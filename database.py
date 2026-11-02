import sqlite3
from pathlib import Path

from models import DatabaseCorruptedError, PLANT_CLASSES, RepottingEvent, WateringEvent


class Database:
    def __init__(self, path):
        self.connection = None
        try:
            self.connection = sqlite3.connect(str(Path(path)))
            self.connection.row_factory = sqlite3.Row
            self.connection.execute('PRAGMA foreign_keys = ON')
            if self.connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise DatabaseCorruptedError('Файл базы данных поврежден.')
            self.connection.executescript('''
                CREATE TABLE IF NOT EXISTS plants (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    species TEXT NOT NULL,
                    plant_type TEXT NOT NULL,
                    lighting TEXT NOT NULL,
                    watering_days INTEGER NOT NULL CHECK(watering_days > 0),
                    repotting_days INTEGER NOT NULL CHECK(repotting_days > 0),
                    planted_on TEXT NOT NULL,
                    soil TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS care_events (
                    id INTEGER PRIMARY KEY,
                    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL CHECK(event_type IN ('watering', 'repotting')),
                    event_date TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    water_ml REAL,
                    fertilizer TEXT,
                    pot_liters REAL,
                    soil TEXT,
                    CHECK (
                        (event_type = 'watering' AND water_ml > 0 AND pot_liters IS NULL)
                        OR (event_type = 'repotting' AND pot_liters > 0 AND water_ml IS NULL)
                    )
                );
            ''')
        except (sqlite3.Error, DatabaseCorruptedError) as error:
            if self.connection:
                self.connection.close()
            raise DatabaseCorruptedError(f'Не удалось открыть базу: {error}') from error

    def plants(self):
        result = []
        for row in self.connection.execute('SELECT * FROM plants ORDER BY name'):
            fields = dict(row)
            plant_type = fields.pop('plant_type')
            result.append(PLANT_CLASSES[plant_type](**fields))
        return result

    def events(self):
        result = []
        for row in self.connection.execute('SELECT * FROM care_events ORDER BY event_date DESC, id DESC'):
            common = dict(plant_id=row['plant_id'], event_date=row['event_date'], notes=row['notes'], id=row['id'])
            if row['event_type'] == 'watering':
                event = WateringEvent(**common, water_ml=row['water_ml'], fertilizer=row['fertilizer'])
            else:
                event = RepottingEvent(**common, pot_liters=row['pot_liters'], soil=row['soil'])
            result.append(event)
        return result

    def save_plant(self, plant, plant_type):
        values = (plant.name, plant.species, plant_type, plant.lighting, plant.watering_days,
                  plant.repotting_days, plant.planted_on.isoformat(), plant.soil)
        if plant.id is None:
            cursor = self.connection.execute('''
                INSERT INTO plants (name, species, plant_type, lighting, watering_days,
                    repotting_days, planted_on, soil) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', values)
            plant.id = cursor.lastrowid
        else:
            self.connection.execute('''
                UPDATE plants SET name=?, species=?, plant_type=?, lighting=?, watering_days=?,
                    repotting_days=?, planted_on=?, soil=? WHERE id=?
            ''', values + (plant.id,))

    def add_event(self, event):
        if isinstance(event, WateringEvent):
            details = ('watering', event.water_ml, event.fertilizer, None, None)
        else:
            details = ('repotting', None, None, event.pot_liters, event.soil)
        return self.connection.execute('''
            INSERT INTO care_events (plant_id, event_date, notes, event_type, water_ml,
                fertilizer, pot_liters, soil) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (event.plant_id, event.event_date.isoformat(), event.notes) + details).lastrowid

    def delete_plant(self, plant_id):
        with self.connection:
            self.connection.execute('DELETE FROM plants WHERE id=?', (plant_id,))

    def delete_event(self, event_id):
        with self.connection:
            self.connection.execute('DELETE FROM care_events WHERE id=?', (event_id,))

    def close(self):
        self.connection.close()
