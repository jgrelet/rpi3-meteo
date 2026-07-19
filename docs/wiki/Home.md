# Documentation technique de rpi-meteo

Le README présente le produit et l'ensemble de ses écrans. Cette documentation regroupe l'installation, la configuration et les détails d'implémentation.

## Guides

- [[Galerie complète de l'interface|Interface-gallery]] : les onze écrans du kiosque et de la station associée ;
- [[Référence technique complète|Technical-reference]] : transports, MQTT, configuration, installation, Docker, PostgreSQL, déploiement et kiosque ;
- [[Validation HC-12|HC12-validation]] : contrôle progressif de la liaison radio bidirectionnelle ;
- [[Docker et PostgreSQL|Docker-and-PostgreSQL]] : volumes, requêtes et permissions.

## Composants

- `app/main.py` : application FastAPI et pages HTML ;
- `app/mqtt_ingestion.py` : réception des mesures MQTT ;
- `app/serial_ingestion.py` et `app/hc12_protocol.py` : passerelle radio ;
- `app/database.py` : persistance PostgreSQL ;
- `app/forecast.py` : récupération des prévisions ;
- `app/air_quality.py` : indicateur relatif issu du BME680 ;
- `scripts/` : déploiement et gestion du kiosque ;
- `tools/` : tests MQTT, radio et tracés distants.
