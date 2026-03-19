import { query } from '../../../../lib/db';

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  const { cityId } = req.query;

  try {
    // Récupérer les données météo les plus récentes
    const result = await query(`
      SELECT 
        c.name as city_name,
        c.country,
        m.metric_type,
        m.value,
        m.unit,
        m.recorded_at
      FROM cities c
      LEFT JOIN metrics m ON c.id = m.city_id
      WHERE c.id = $1 
        AND (m.source = 'OpenWeatherMap' OR m.source IS NULL)
        AND m.recorded_at > NOW() - INTERVAL '2 hours'
      ORDER BY m.recorded_at DESC
    `, [cityId]);

    if (result.rows.length === 0) {
      return res.status(404).json({ 
        error: 'No recent weather data found',
        suggestion: `Call POST /api/weather/update/${cityId} first`
      });
    }

    // Organiser les données par type de métrique
    const weatherData = {
      city: result.rows[0].city_name,
      country: result.rows[0].country,
      last_updated: result.rows[0].recorded_at,
      metrics: {}
    };

    result.rows.forEach(row => {
      if (row.metric_type) {
        weatherData.metrics[row.metric_type] = {
          value: parseFloat(row.value),
          unit: row.unit,
          recorded_at: row.recorded_at
        };
      }
    });

    res.status(200).json(weatherData);

  } catch (error) {
    console.error('Current weather error:', error);
    res.status(500).json({ 
      error: 'Failed to get current weather data',
      details: error.message 
    });
  }
}
