import { query } from '../../../lib/db';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  const OPENWEATHER_API_KEY = process.env.OPENWEATHER_API_KEY;

  try {
    // Récupérer toutes les villes
    const citiesResult = await query(
      'SELECT id, name, latitude, longitude FROM cities ORDER BY id'
    );

    const cities = citiesResult.rows;
    const results = [];

    // Mettre à jour chaque ville (avec délai pour éviter rate limiting)
    for (const city of cities) {
      try {
        // Appel OpenWeatherMap
        const weatherResponse = await fetch(
          `https://api.openweathermap.org/data/2.5/weather?lat=${city.latitude}&lon=${city.longitude}&appid=${OPENWEATHER_API_KEY}&units=metric&lang=fr`
        );

        if (weatherResponse.ok) {
          const weatherData = await weatherResponse.json();

          // Supprimer anciennes données
          await query(
            `DELETE FROM metrics 
             WHERE city_id = $1 AND source = 'OpenWeatherMap' 
             AND recorded_at < NOW() - INTERVAL '1 hour'`,
            [city.id]
          );

          // Insérer nouvelles données
          const metrics = [
            ['temperature', weatherData.main.temp, '°C'],
            ['humidity', weatherData.main.humidity, '%'],
            ['pressure', weatherData.main.pressure, 'hPa'],
            ['wind_speed', weatherData.wind?.speed || 0, 'm/s'],
            ['visibility', (weatherData.visibility || 0) / 1000, 'km']
          ];

          for (const [type, value, unit] of metrics) {
            await query(
              `INSERT INTO metrics (city_id, metric_type, value, unit, source, recorded_at)
               VALUES ($1, $2, $3, $4, 'OpenWeatherMap', NOW())`,
              [city.id, type, value, unit]
            );
          }

          results.push({
            city: city.name,
            status: 'success',
            temperature: weatherData.main.temp,
            description: weatherData.weather[0].description
          });
        } else {
          results.push({
            city: city.name,
            status: 'error',
            error: `API error: ${weatherResponse.status}`
          });
        }

        // Délai pour éviter rate limiting (60 calls/min max)
        await new Promise(resolve => setTimeout(resolve, 1100));

      } catch (error) {
        results.push({
          city: city.name,
          status: 'error',
          error: error.message
        });
      }
    }

    res.status(200).json({
      success: true,
      updated_at: new Date().toISOString(),
      cities_updated: results.filter(r => r.status === 'success').length,
      total_cities: cities.length,
      results
    });

  } catch (error) {
    console.error('Bulk weather update error:', error);
    res.status(500).json({ 
      error: 'Failed to update weather data for all cities',
      details: error.message 
    });
  }
}
