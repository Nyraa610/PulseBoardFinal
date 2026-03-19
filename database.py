import os
import asyncpg
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configuration du logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.pool = None
        logger.info("✅ DatabaseManager initialized with Neon PostgreSQL")

    async def connect(self):
        """Établit la connexion à la base de données"""
        try:
            if not self.pool:
                self.pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Connected to Neon PostgreSQL database")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            return False

    async def disconnect(self):
        """Ferme la connexion à la base de données"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("✅ Disconnected from database")

    async def execute_query(self, query: str, *args):
        """Exécute une requête avec paramètres"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as connection:
                return await connection.fetch(query, *args)
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            raise

    async def execute_single(self, query: str, *args):
        """Exécute une requête qui retourne un seul résultat"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as connection:
                return await connection.fetchrow(query, *args)
        except Exception as e:
            logger.error(f"❌ Single query execution failed: {e}")
            raise

    async def execute_command(self, query: str, *args):
        """Exécute une commande (INSERT, UPDATE, DELETE)"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as connection:
                return await connection.execute(query, *args)
        except Exception as e:
            logger.error(f"❌ Command execution failed: {e}")
            raise

    # ===============================
    # MÉTHODES POUR LES VILLES
    # ===============================
    
    async def get_all_cities(self):
        """Récupère toutes les villes"""
        query = "SELECT * FROM cities ORDER BY name"
        return await self.execute_query(query)

    async def get_city_by_name(self, name: str):
        """Récupère une ville par son nom"""
        query = "SELECT * FROM cities WHERE LOWER(name) = LOWER($1)"
        return await self.execute_single(query, name)

    async def get_city_by_id(self, city_id: int):
        """Récupère une ville par son ID"""
        query = "SELECT * FROM cities WHERE id = $1"
        return await self.execute_single(query, city_id)

    async def create_city(self, name: str, country: str, latitude: float, longitude: float):
        """Crée une nouvelle ville"""
        query = """
        INSERT INTO cities (name, country, latitude, longitude, created_at)
        VALUES ($1, $2, $3, $4, NOW())
        RETURNING *
        """
        return await self.execute_single(query, name, country, latitude, longitude)

    # ===============================
    # MÉTHODES POUR LES ÉVÉNEMENTS
    # ===============================
    
    async def get_all_events(self):
        """Récupère tous les événements"""
        query = """
        SELECT e.*, c.name as city_name 
        FROM events e 
        LEFT JOIN cities c ON e.city_id = c.id 
        ORDER BY e.start_date DESC
        """
        return await self.execute_query(query)

    async def get_events_by_city(self, city_id: int):
        """Récupère les événements d'une ville"""
        query = """
        SELECT e.*, c.name as city_name 
        FROM events e 
        LEFT JOIN cities c ON e.city_id = c.id 
        WHERE e.city_id = $1 
        ORDER BY e.start_date DESC
        """
        return await self.execute_query(query, city_id)

    async def create_event(self, event_data: Dict[str, Any]):
        """Crée un nouvel événement"""
        query = """
        INSERT INTO events (title, description, start_date, end_date, location, 
                          category, price, city_id, external_id, source, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        RETURNING *
        """
        return await self.execute_single(
            query,
            event_data.get('title'),
            event_data.get('description'),
            event_data.get('start_date'),
            event_data.get('end_date'),
            event_data.get('location'),
            event_data.get('category'),
            event_data.get('price'),
            event_data.get('city_id'),
            event_data.get('external_id'),
            event_data.get('source', 'manual')
        )

    # ===============================
    # MÉTHODES POUR LES MÉTRIQUES
    # ===============================
    
    async def get_all_metrics(self):
        """Récupère toutes les métriques"""
        query = """
        SELECT m.*, c.name as city_name 
        FROM metrics m 
        LEFT JOIN cities c ON m.city_id = c.id 
        ORDER BY m.recorded_at DESC
        """
        return await self.execute_query(query)

    async def get_metrics_by_city(self, city_id: int):
        """Récupère les métriques d'une ville"""
        query = """
        SELECT m.*, c.name as city_name 
        FROM metrics m 
        LEFT JOIN cities c ON m.city_id = c.id 
        WHERE m.city_id = $1 
        ORDER BY m.recorded_at DESC
        """
        return await self.execute_query(query, city_id)

    async def create_metric(self, metric_data: Dict[str, Any]):
        """Crée une nouvelle métrique"""
        query = """
        INSERT INTO metrics (city_id, metric_type, value, unit, source, recorded_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        RETURNING *
        """
        return await self.execute_single(
            query,
            metric_data.get('city_id'),
            metric_data.get('metric_type'),
            metric_data.get('value'),
            metric_data.get('unit'),
            metric_data.get('source', 'manual')
        )

    # ===============================
    # MÉTHODES POUR LES SCORES URBAINS
    # ===============================
    
    async def get_all_urban_scores(self):
        """Récupère tous les scores urbains"""
        query = """
        SELECT us.*, c.name as city_name 
        FROM urban_scores us 
        LEFT JOIN cities c ON us.city_id = c.id 
        ORDER BY us.calculated_at DESC
        """
        return await self.execute_query(query)

    async def get_urban_score_by_city(self, city_id: int):
        """Récupère le score urbain d'une ville"""
        query = """
        SELECT us.*, c.name as city_name 
        FROM urban_scores us 
        LEFT JOIN cities c ON us.city_id = c.id 
        WHERE us.city_id = $1 
        ORDER BY us.calculated_at DESC 
        LIMIT 1
        """
        return await self.execute_single(query, city_id)

    async def save_urban_score(self, city_id: int, score_data: Dict[str, Any]):
        """Sauvegarde un score urbain"""
        query = """
        INSERT INTO urban_scores (
            city_id, overall_score, weather_score, air_quality_score, 
            events_score, transport_score, calculated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        RETURNING *
        """
        return await self.execute_single(
            query,
            city_id,
            score_data.get('overall_score'),
            score_data.get('weather_score'),
            score_data.get('air_quality_score'),
            score_data.get('events_score'),
            score_data.get('transport_score')
        )

    # ===============================
    # MÉTHODES POUR LES DONNÉES MÉTÉO
    # ===============================
    
    async def save_weather_data(self, city_id: int, weather_data: Dict[str, Any]):
        """Sauvegarde les données météo"""
        query = """
        INSERT INTO weather_data (
            city_id, temperature, humidity, pressure, wind_speed, 
            weather_condition, recorded_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        RETURNING *
        """
        return await self.execute_single(
            query,
            city_id,
            weather_data.get('temperature'),
            weather_data.get('humidity'),
            weather_data.get('pressure'),
            weather_data.get('wind_speed'),
            weather_data.get('weather_condition')
        )

    async def get_latest_weather(self, city_id: int):
        """Récupère les dernières données météo d'une ville"""
        query = """
        SELECT * FROM weather_data 
        WHERE city_id = $1 
        ORDER BY recorded_at DESC 
        LIMIT 1
        """
        return await self.execute_single(query, city_id)

    # ===============================
    # MÉTHODES DE TEST
    # ===============================
    
    async def test_connection(self):
        """Test la connexion à la base de données"""
        try:
            await self.connect()
            result = await self.execute_single("SELECT 1 as test")
            return {"status": "success", "test_result": dict(result) if result else None}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# Instance globale
db = DatabaseManager()
