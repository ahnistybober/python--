import json
from datetime import date

from models import PLANT_CLASSES, PlantCareError, RepottingEvent, WateringEvent


class AIAdapter:
    def __init__(self, manager):
        self.manager = manager

    def save_task(self, path):
        example = {
            'plants': [dict(name='Монстера у окна', species='Monstera deliciosa',
                            plant_type='Тропическое', lighting='Рассеянный свет', watering_days=7,
                            repotting_days=365, planted_on=date.today().isoformat(),
                            soil='Грунт для ароидных с перлитом')],
            'events': []
        }
        task = ('Заполни начальные данные домашних растений по моему списку. '
                'Верни только JSON по структуре примера, без Markdown. '
                'plant_type: Обычное, Суккулент или Тропическое. '
                'lighting: Прямое солнце, Рассеянный свет или Полутень. '
                'Интервалы — целые числа дней от 1 до 3650. Даты — ГГГГ-ММ-ДД, '
                f'не позже {date.today().isoformat()}. Дату начала учета уточни у меня. '
                'Рекомендации по уходу согласуй с условиями содержания. '
                'Не придумывай выполненные поливы и пересадки. '
                'Если истории нет, events оставь пустым. '
                'У события plant_index — номер растения в plants, начиная с нуля. '
                'Для полива поля: plant_index, event_type="watering", event_date, '
                'water_ml, fertilizer, notes. Для пересадки: plant_index, '
                'event_type="repotting", event_date, pot_liters, soil, notes. '
                'Дата события не должна быть раньше planted_on.\n\n'
                + json.dumps(example, ensure_ascii=False, indent=2))
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(task)

    def read_file(self, path):
        with open(path, encoding='utf-8-sig') as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or set(data) != {'plants', 'events'}:
            raise PlantCareError('В JSON нужны списки plants и events.')
        if not isinstance(data['plants'], list) or not isinstance(data['events'], list):
            raise PlantCareError('plants и events должны быть списками.')
        plants = []
        events = []
        for index, record in enumerate(data['plants']):
            try:
                fields = dict(record)
                kind = fields.pop('plant_type')
                if 'id' in fields:
                    raise PlantCareError('Не задавайте внутренний id растения.')
                plants.append((PLANT_CLASSES[kind](**fields), kind))
            except (TypeError, ValueError, KeyError, PlantCareError) as error:
                raise PlantCareError(f'Растение {index + 1}: {error}') from error
        for index, record in enumerate(data['events']):
            try:
                fields = dict(record)
                plant_index = fields.pop('plant_index')
                if type(plant_index) is not int or not 0 <= plant_index < len(plants):
                    raise PlantCareError('Неверный plant_index.')
                kind = fields.pop('event_type')
                if kind not in ('watering', 'repotting') or 'id' in fields:
                    raise PlantCareError('Неверный тип или лишний id события.')
                cls = WateringEvent if kind == 'watering' else RepottingEvent
                event = cls(plant_index, **fields)
                event.validate(plants[plant_index][0])
                events.append(event)
            except (TypeError, ValueError, KeyError, PlantCareError) as error:
                raise PlantCareError(f'Событие {index + 1}: {error}') from error
        return plants, events

    def import_data(self, plants, events):
        with self.manager.database.connection:
            for plant, kind in plants:
                self.manager.database.save_plant(plant, kind)
            for event in events:
                event.plant_id = plants[event.plant_id][0].id
                self.manager.database.add_event(event)
        self.manager.refresh()
