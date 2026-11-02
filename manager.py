import csv
from datetime import date, timedelta
from math import floor

from models import LIGHTING, PLANT_CLASSES, PlantCareError, PlantNotFoundError, WateringEvent


class PlantCareManager:
    def __init__(self, database):
        self.database = database
        self.refresh()

    def refresh(self):
        self.plants = self.database.plants()
        self.events = self.database.events()
        self.statuses = {p.id: self.predict(p) for p in self.plants}
        self.lighting = {light: [p.id for p in self.plants if p.lighting == light] for light in LIGHTING}

    def find_plant(self, plant_id):
        for plant in self.plants:
            if plant.id == plant_id:
                return plant
        raise PlantNotFoundError('Растение не найдено.')

    def save_plant(self, fields, plant_id=None):
        fields = dict(fields)
        plant_type = fields.pop('plant_type')
        if plant_type not in PLANT_CLASSES:
            raise PlantCareError('Выберите тип растения.')
        if plant_id is not None:
            self.find_plant(plant_id)
        plant = PLANT_CLASSES[plant_type](**fields, id=plant_id)
        for event in self.events:
            if event.plant_id == plant_id:
                event.validate(plant)
        with self.database.connection:
            self.database.save_plant(plant, plant_type)
        self.refresh()

    def record_event(self, event):
        event.validate(self.find_plant(event.plant_id))
        with self.database.connection:
            self.database.add_event(event)
        self.refresh()

    def predict(self, plant):
        watering = sorted({e.event_date for e in self.events
                           if e.plant_id == plant.id and isinstance(e, WateringEvent)})[-6:]
        intervals = [(b - a).days for a, b in zip(watering, watering[1:])]
        average = plant.watering_days
        if intervals:
            weights = range(1, len(intervals) + 1)
            actual = sum(w * days for w, days in zip(weights, intervals)) / sum(weights)
            share = len(intervals) / 5
            average = (1 - share) * plant.watering_days + share * actual
        interval = max(1, floor(plant.watering_interval(average) + 0.5))
        last = watering[-1] if watering else plant.planted_on
        next_date = last + timedelta(days=interval)
        days_left = (next_date - date.today()).days
        status = 'Полив не требуется'
        if days_left <= 0:
            status = 'Требует полива'
        if days_left <= -plant.urgent_after():
            status = 'Срочный полив'
        repots = [e.event_date for e in self.events
                  if e.plant_id == plant.id and not isinstance(e, WateringEvent)]
        repot_date = max(repots, default=plant.planted_on) + timedelta(days=plant.repotting_days)
        return dict(next_date=next_date, days_left=days_left, status=status,
                    interval=interval, repot_date=repot_date)

    def statistics(self, events=None):
        events = self.events if events is None else events
        result = {}
        for kind, cls in PLANT_CLASSES.items():
            plants = [p for p in self.plants if type(p) is cls]
            ids = {p.id for p in plants}
            volumes = [e.water_ml for e in events if e.plant_id in ids and isinstance(e, WateringEvent)]
            intervals = []
            for plant in plants:
                dates = sorted({e.event_date for e in events
                                if e.plant_id == plant.id and isinstance(e, WateringEvent)})
                intervals.extend((b - a).days for a, b in zip(dates, dates[1:]))
            result[kind] = dict(count=len(plants), avg_water_ml=sum(volumes) / len(volumes) if volumes else None,
                                avg_interval_days=sum(intervals) / len(intervals) if intervals else None)
        return result

    def export_csv(self, path):
        with open(path, 'w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('plant_id', 'date', 'water_ml', 'fertilizer', 'notes'))
            for event in self.events:
                if isinstance(event, WateringEvent):
                    writer.writerow((event.plant_id, event.event_date.isoformat(), event.water_ml,
                                     event.fertilizer, event.notes))

    def import_csv(self, path):
        pending = []
        existing = {(e.plant_id, e.event_date, e.water_ml, e.fertilizer, e.notes)
                    for e in self.events if isinstance(e, WateringEvent)}
        with open(path, encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['plant_id', 'date', 'water_ml', 'fertilizer', 'notes']:
                raise PlantCareError('Неверные колонки CSV. Используйте файл экспорта приложения.')
            for line, row in enumerate(reader, 2):
                try:
                    event = WateringEvent(int(row['plant_id']), row['date'], row['water_ml'],
                                          row['fertilizer'], row['notes'])
                    event.validate(self.find_plant(event.plant_id))
                except (ValueError, TypeError, PlantCareError) as error:
                    raise PlantCareError(f'Строка {line}: {error}') from error
                key = (event.plant_id, event.event_date, event.water_ml, event.fertilizer, event.notes)
                if key not in existing:
                    pending.append(event)
                    existing.add(key)
        with self.database.connection:
            for event in pending:
                self.database.add_event(event)
        self.refresh()
        return len(pending)
