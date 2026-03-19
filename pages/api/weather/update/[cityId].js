import { query } from '../../../../lib/db';

export default async function handler(req, res) {
  if (req.method !== 'POST' && req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  const { cityId } = req.query;
  const OPENWEATHER_API_KEY = process.env.OPENWEATHER_API_KEY;

  try {
    // 1. Récupérer les coordonnées de la ville depuis la base
    const cityResult = await query(
      'SELECT id, name, latitude, longitude FROM cities WHERE id = $1',
      [cityId]
    );

    if (cityResult.rows.length === 0) {
      return res.status(404).json({ error: 'City not found' });
    }

    const city = cityResult.rows[0];

    // 2. Appel à OpenWeatherMap
    const weatherResponse = await fetch(
      `https://api.openweathermap.org/data/2.5/weather?lat=${city.latitude}&lon=${city.longitude}&appid=${OPENWEATHER_API_KEY}&units=metric&lang=fr`
    );

    if (!weatherResponse.ok) {
      throw new Error(`OpenWeather API error: ${weatherResponse.status}`);
    }

    const weatherData = await weatherResponse.json();

    // 3. Extraire les données importantes
    const metrics = [
      {
        type: 'temperature',
        value: weatherData.main.temp,
        unit: '°C'
      },
      {
        type: 'humidity',
        value: weatherData.main.humidity,
        unit: '%'
      },
      {
        type: 'pressure',
        value: weatherData.main.pressure,
        unit: 'hPa'
      },
      {
        type: 'wind_speed',
        value: weatherData.wind?.speed || 0,
        unit: 'm/s'
      },
      {
        type: 'visibility',
        value: (weatherData.visibility || 0) / 1000, // Convertir en km
        unit: 'km'
      }
    ];

    // 4. Supprimer les anciennes métriques météo de la ville
    await query(
      `DELETE FROM metrics 
       WHERE city_id = $1 
       AND source = 'OpenWeatherMap' 
       AND recorded_at < NOW() - INTERVAL '1 hour'`,
      [cityId]
    );

    // 5. Insérer les nouvelles métriques
    const insertPromises = metrics.map(metric =>
      query(
        `INSERT INTO metrics (city_id, metric_type, value, unit, source, recorded_at)
         VALUES ($1, $2, $3, $4, $5, NOW())`,
        [cityId, metric.type, metric.value, metric.unit, 'OpenWeatherMap']
      )
    );

    await Promise.all(insertPromises);

    // 6. Récupérer les données sauvegardées
    const savedMetrics = await query(
      `SELECT metric_type, value, unit, recorded_at 
       FROM metrics 
       WHERE city_id = $1 AND source = 'OpenWeatherMap'
       ORDER BY recorded_at DESC`,
      [cityId]
    );

    res.status(200).json({
      success: true,
      city: city.name,
      updated_at: new Date().toISOString(),
      weather_data: {
        description: weatherData.weather[0].description,
        icon: weatherData.weather[0].icon,
        raw_data: weatherData
      },
      metrics: savedMetrics.rows
    });

  } catch (error) {
    console.error('Weather update error:', error);
    res.status(500).json({ 
      error: 'Failed to update weather data',
      details: error.message 
    });
  }
}
