import asyncpg
import os
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.connection_string = os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_URL environment variable is required")
    
    async def get_connection(self):
        """Crée une connexion à la base de données"""
        return await asyncpg.connect(self.connection_string)
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Exécute une requête SELECT et retourne les résultats"""
        conn = await self.get_connection()
        try:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
        finally:
            await conn.close()
    
    async def execute_command(self, command: str, *args) -> str:
        """Exécute une commande INSERT/UPDATE/DELETE"""
        conn = await self.get_connection()
        try:
            result = await conn.execute(command, *args)
            return result
        finally:
            await conn.close()
    
    # CITIES
    async def get_cities(self) -> List[Dict[str, Any]]:
        """Récupère toutes les villes"""
        query = "SELECT * FROM cities ORDER BY name"
        return await self.execute_query(query)
    
    async def get_city_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Récupère une ville par son nom"""
        query = "SELECT * FROM cities WHERE name = $1"
        results = await self.execute_query(query, name)
        return results[0] if results else None
    
    async def create_city(self, name: str, latitude: float, longitude: float, 
                         country_code: str = "FR", timezone: str = "Europe/Paris") -> int:
        """Crée une nouvelle ville"""
        query = """
        INSERT INTO cities (name, latitude, longitude, country_code, timezone)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
        """
        conn = await self.get_connection()
        try:
            city_id = await conn.fetchval(query, name, latitude, longitude, country_code, timezone)
            return city_id
        finally:
            await conn.close()
    
    # WEATHER DATA
    async def save_weather_data(self, city_id: int, weather_data: Dict[str, Any]) -> None:
        """Sauvegarde les données météo"""
        query = """
        INSERT INTO weather_data (
            city_id, timestamp, temperature, feels_like, humidity, pressure,
            wind_speed, wind_direction, weather_main, weather_description,
            icon, visibility, uv_index
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """
        await self.execute_command(
            query, city_id, datetime.now(), weather_data.get('temperature'),
            weather_data.get('feels_like'), weather_data.get('humidity'),
            weather_data.get('pressure'), weather_data.get('wind_speed'),
            weather_data.get('wind_direction'), weather_data.get('weather_main'),
            weather_data.get('weather_description'), weather_data.get('icon'),
            weather_data.get('visibility'), weather_data.get('uv_index')
        )
    
    async def get_latest_weather(self, city_id: int) -> Optional[Dict[str, Any]]:
        """Récupère les dernières données météo pour une ville"""
        query = """
        SELECT * FROM weather_data 
        WHERE city_id = $1 
        ORDER BY timestamp DESC 
        LIMIT 1
        """
        results = await self.execute_query(query, city_id)
        return results[0] if results else None
    
    # AIR QUALITY
    async def save_air_quality(self, city_id: int, air_data: Dict[str, Any]) -> None:
        """Sauvegarde les données de qualité de l'air"""
        query = """
        INSERT INTO air_quality (
            city_id, timestamp, aqi, pm25, pm10, no2, o3, co, so2, health_advice
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        await self.execute_command(
            query, city_id, datetime.now(), air_data.get('aqi'),
            air_data.get('pm25'), air_data.get('pm10'), air_data.get('no2'),
            air_data.get('o3'), air_data.get('co'), air_data.get('so2'),
            air_data.get('health_advice')
        )
    
    async def get_latest_air_quality(self, city_id: int) -> Optional[Dict[str, Any]]:
        """Récupère les dernières données de qualité de l'air"""
        query = """
        SELECT * FROM air_quality 
        WHERE city_id = $1 
        ORDER BY timestamp DESC 
        LIMIT 1
        """
        results = await self.execute_query(query, city_id)
        return results[0] if results else None
    
    # EVENTS
    async def save_event(self, city_id: int, event_data: Dict[str, Any]) -> None:
        """Sauvegarde un événement"""
        query = """
        INSERT INTO events (
            city_id, title, description, start_date, end_date, 
            location, category, source, external_id, url
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        await self.execute_command(
            query, city_id, event_data.get('title'), event_data.get('description'),
            event_data.get('start_date'), event_data.get('end_date'),
            event_data.get('location'), event_data.get('category'),
            event_data.get('source'), event_data.get('external_id'),
            event_data.get('url')
        )
    
    async def get_city_events(self, city_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les événements d'une ville"""
        query = """
        SELECT * FROM events 
        WHERE city_id = $1 AND start_date >= NOW()
        ORDER BY start_date ASC 
        LIMIT $2
        """
        return await self.execute_query(query, city_id, limit)
    
    # URBAN SCORES
    async def save_urban_score(self, city_id: int, score_data: Dict[str, Any]) -> None:
        """Sauvegarde un score urbain"""
        query = """
        INSERT INTO urban_scores (
            city_id, date, score, weather_score, air_quality_score, 
            events_score, calculation_details
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await self.execute_command(
            query, city_id, datetime.now().date(), score_data.get('score'),
            score_data.get('weather_score'), score_data.get('air_quality_score'),
            score_data.get('events_score'), json.dumps(score_data.get('calculation_details', {}))
        )
    
    async def get_latest_urban_score(self, city_id: int) -> Optional[Dict[str, Any]]:
        """Récupère le dernier score urbain"""
        query = """
        SELECT * FROM urban_scores 
        WHERE city_id = $1 
        ORDER BY date DESC 
        LIMIT 1
        """
        results = await self.execute_query(query, city_id)
        return results[0] if results else None
    
    # PULSE DATA (pour compatibilité)
    async def save_pulse_data(self, city: str, data_type: str, data: Dict[str, Any]) -> None:
        """Sauvegarde des données pulse"""
        query = """
        INSERT INTO pulse_data (city, data_type, data)
        VALUES ($1, $2, $3)
        """
        await self.execute_command(query, city, data_type, json.dumps(data))
    
    # API LOGS
    async def log_api_call(self, endpoint: str, city_id: Optional[int] = None, 
                          response_time_ms: Optional[int] = None, 
                          status_code: Optional[int] = None,
                          error_message: Optional[str] = None) -> None:
        """Log un appel API"""
        query = """
        INSERT INTO api_logs (endpoint, city_id, response_time_ms, status_code, error_message)
        VALUES ($1, $2, $3, $4, $5)
        """
        await self.execute_command(query, endpoint, city_id, response_time_ms, status_code, error_message)

# Instance globale
db = DatabaseManager()
