# Docker memo

Commandes utiles pour inspecter les conteneurs et les volumes Docker du projet
`rpi-meteo`, en particulier la base PostgreSQL.

## PostgreSQL

Dans `docker-compose.yml`, PostgreSQL utilise un volume Docker nomme :

```yaml
postgres_data:/var/lib/postgresql/data
```

`/var/lib/postgresql/data` est donc le chemin dans le conteneur PostgreSQL, pas
un dossier directement visible sous `/var/lib` sur l'hote Raspberry Pi.

Sur l'hote, Docker stocke le volume sous `/var/lib/docker/volumes/...`, par
exemple :

```bash
/var/lib/docker/volumes/rpi-meteo_postgres_data/_data
```

Le nom exact peut varier selon le nom du projet Compose.

## Lister et localiser les volumes

Lister les volumes Docker :

```bash
docker volume ls
```

Trouver les volumes lies a PostgreSQL :

```bash
docker volume ls | grep postgres
```

Afficher le detail d'un volume et son chemin reel sur l'hote :

```bash
docker volume inspect rpi-meteo_postgres_data
```

Le champ `Mountpoint` donne le chemin exact sur l'hote.

## Inspecter les fichiers PostgreSQL

Depuis le conteneur PostgreSQL :

```bash
docker exec -it rpi-meteo-postgres ls -la /var/lib/postgresql/data
```

Depuis un conteneur temporaire, sans acceder directement a `/var/lib/docker` :

```bash
docker run --rm -it -v rpi-meteo_postgres_data:/data alpine ls -la /data
```

Si un acces direct au filesystem hote est necessaire, il faut generalement
utiliser `sudo`, meme si l'utilisateur est dans le groupe `docker` :

```bash
sudo ls -la /var/lib/docker/volumes/rpi-meteo_postgres_data/_data
```

## Taille utilisee par la base

Taille logique de la base PostgreSQL :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "SELECT pg_size_pretty(pg_database_size('rpi_meteo')) AS database_size;"
```

Taille par table, index inclus :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  relname AS table,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  pg_size_pretty(pg_relation_size(relid)) AS table_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
"
```

Taille totale du repertoire de donnees PostgreSQL dans le volume Docker :

```bash
docker run --rm -v rpi-meteo_postgres_data:/data alpine du -sh /data
```

Cette taille inclut les fichiers PostgreSQL sur disque : donnees, index, WAL et
metadonnees internes. Elle peut donc etre differente de `pg_database_size`.

## Requetes utiles

Ouvrir une session `psql` interactive dans la base :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo
```

Lister les tables et vues :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "\dt"
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "\dv"
```

Afficher la structure d'une table ou d'une vue :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "\d sensor_readings"
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "\d hourly_sensor_stats"
```

Compter les messages bruts et les mesures capteurs :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "SELECT count(*) AS raw_messages FROM raw_messages;"
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "SELECT count(*) AS sensor_readings FROM sensor_readings;"
```

Connaitre la periode couverte par les donnees stockees :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  min(recorded_at) AS first_recorded_at,
  max(recorded_at) AS last_recorded_at
FROM sensor_readings;
"
```

Compter les heures distinctes contenant des mesures numeriques :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT count(DISTINCT recorded_hour) AS stored_hours
FROM sensor_series_numeric;
"
```

Compter les lignes horaires agregees, par capteur :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  sensor_name,
  unit,
  count(*) AS hourly_rows,
  min(recorded_hour) AS first_hour,
  max(recorded_hour) AS last_hour
FROM hourly_sensor_stats
GROUP BY sensor_name, unit
ORDER BY sensor_name, unit;
"
```

Afficher les dernieres valeurs connues par capteur :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  sensor_name,
  numeric_value,
  text_value,
  unit,
  recorded_at
FROM latest_sensor_values
ORDER BY sensor_name;
"
```

Afficher les derniers messages recus :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  id,
  source,
  channel,
  export_mode,
  topic,
  recorded_at
FROM raw_messages
ORDER BY recorded_at DESC
LIMIT 10;
"
```

Afficher les dernieres mesures capteurs :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  sensor_name,
  numeric_value,
  text_value,
  unit,
  recorded_at
FROM sensor_readings
ORDER BY recorded_at DESC
LIMIT 20;
"
```

Afficher les moyennes horaires recentes :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  recorded_hour,
  sensor_name,
  samples,
  avg_value,
  min_value,
  max_value,
  unit
FROM hourly_sensor_stats
WHERE recorded_hour >= now() - interval '24 hours'
ORDER BY recorded_hour DESC, sensor_name
LIMIT 100;
"
```

Compter les donnees par mode d'export :

```bash
docker exec -it rpi-meteo-postgres psql -U jgrelet -d rpi_meteo -c "
SELECT
  export_mode,
  count(*) AS readings,
  min(recorded_at) AS first_recorded_at,
  max(recorded_at) AS last_recorded_at
FROM sensor_readings
GROUP BY export_mode
ORDER BY export_mode;
"
```

## Permissions

Etre dans le groupe `docker` permet d'utiliser l'API Docker sans `sudo`, par
exemple `docker ps` ou `docker volume inspect`.

Cela ne donne pas automatiquement le droit Unix de lire directement
`/var/lib/docker` :

```bash
ls /var/lib/docker
```

peut donc retourner :

```text
Permission denied
```

Dans ce cas, utiliser les commandes Docker ci-dessus ou passer par `sudo` pour
l'acces direct au filesystem hote.
