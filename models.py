from datetime import date, datetime
from math import isfinite


LIGHTING = ('Прямое солнце', 'Рассеянный свет', 'Полутень')
PLANT_TYPES = ('Обычное', 'Суккулент', 'Тропическое')


class PlantCareError(Exception):
    pass


class NegativeWaterVolumeError(PlantCareError):
    pass


class InvalidCareDateError(PlantCareError):
    pass


class PlantNotFoundError(PlantCareError):
    pass


class DatabaseCorruptedError(PlantCareError):
    pass


def read_date(value):
    if isinstance(value, date):
        result = value
    else:
        result = None
        for pattern in ('%d.%m.%Y', '%Y-%m-%d'):
            try:
                result = datetime.strptime(str(value).strip(), pattern).date()
                break
            except ValueError:
                continue
        if result is None:
            raise InvalidCareDateError('Введите дату в формате ДД.ММ.ГГГГ.')
    if result > date.today():
        raise InvalidCareDateError('Дата не может быть в будущем.')
    return result


def read_number(value):
    try:
        result = float(str(value).replace(',', '.'))
    except ValueError:
        raise PlantCareError('Введите число.') from None
    if not isfinite(result):
        raise PlantCareError('Введите конечное число.')
    return result


def read_interval(value):
    result = read_number(value)
    if not result.is_integer() or not 1 <= result <= 3650:
        raise PlantCareError('Интервал должен быть целым числом от 1 до 3650 дней.')
    return int(result)


class Plant:
    def __init__(self, name, species, lighting, watering_days, planted_on,
                 repotting_days=365, soil='', id=None):
        self.id = id
        self.name = str(name).strip()
        self.species = str(species).strip()
        self.lighting = lighting
        self.watering_days = read_interval(watering_days)
        self.repotting_days = read_interval(repotting_days)
        self.planted_on = read_date(planted_on)
        self.soil = str(soil).strip()
        if not self.name or not self.species:
            raise PlantCareError('Укажите имя и вид растения.')
        if lighting not in LIGHTING:
            raise PlantCareError('Выберите освещение из списка.')

    def watering_interval(self, average):
        return max(self.watering_days * 0.5, min(average, self.watering_days * 2))

    def urgent_after(self):
        return 2


class SucculentPlant(Plant):
    def watering_interval(self, average):
        return max(self.watering_days * 0.8, min(average, self.watering_days * 2))

    def urgent_after(self):
        return 3


class TropicalPlant(Plant):
    def watering_interval(self, average):
        return max(self.watering_days * 0.5, min(average, self.watering_days * 1.25))

    def urgent_after(self):
        return 1


PLANT_CLASSES = dict(zip(PLANT_TYPES, (Plant, SucculentPlant, TropicalPlant)))


class CareEvent:
    def __init__(self, plant_id, event_date, notes='', id=None):
        self.id = id
        self.plant_id = plant_id
        self.event_date = read_date(event_date)
        self.notes = str(notes).strip()

    def validate(self, plant):
        if self.event_date < plant.planted_on:
            raise InvalidCareDateError('Дата ухода не может быть раньше посадки.')


class WateringEvent(CareEvent):
    def __init__(self, plant_id, event_date, water_ml, fertilizer='', notes='', id=None):
        super().__init__(plant_id, event_date, notes, id)
        self.water_ml = read_number(water_ml)
        self.fertilizer = str(fertilizer).strip()
        if self.water_ml < 0:
            raise NegativeWaterVolumeError('Объем воды не может быть отрицательным.')
        if self.water_ml == 0:
            raise PlantCareError('Объем воды должен быть больше нуля.')


class RepottingEvent(CareEvent):
    def __init__(self, plant_id, event_date, pot_liters, soil, notes='', id=None):
        super().__init__(plant_id, event_date, notes, id)
        self.pot_liters = read_number(pot_liters)
        self.soil = str(soil).strip()
        if self.pot_liters <= 0 or not self.soil:
            raise PlantCareError('Укажите положительный объем горшка и грунт.')
