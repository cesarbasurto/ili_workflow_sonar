# Usar host.docker.internal en linux

Cuando desees utilizar tu base de datos de tu host en postgres a través de host.docker.internal debes realizar la siguiente configuración:

1. Primero mira la IP del puente en el host:

```shell
ip addr show docker0 | grep 'inet '
```

2. Habilitar conexiones externas en postgres

*Importante*: habilitar que PostgreSQL escuche conexiones “externas”

Por defecto en Ubuntu, PostgreSQL escucha solo en localhost. 

## Verifica PostgreSQL en el host Ubuntu

Ejecuta en el host:
``` 
sudo systemctl status postgresql --no-pager
```

Luego:

```
sudo pg_lsclusters
```

## Configura PostgreSQL para escuchar conexiones Docker

Abre el archivo indicado por SHOW config_file;. Generalmente estará en una ruta como:

/etc/postgresql/18/main/postgresql.conf

Edítalo:

```
sudo vim /etc/postgresql/18/main/postgresql.conf
```

Busca:

#listen_addresses = 'localhost'

Para permitir conexiones desde la red Docker puedes usar:

```
listen_addresses = '*'
port = 5432
```

El parámetro listen_addresses determina las interfaces TCP/IP donde PostgreSQL acepta conexiones y requiere reiniciar el servidor para aplicar el cambio.

No significa que cualquier persona podrá conectarse automáticamente: pg_hba.conf, las credenciales y el firewall seguirán controlando el acceso.

## Autoriza solamente la red Docker

Primero averigua la subred de Docker:

```
docker network inspect bridge \
  --format '{{(index .IPAM.Config 0).Subnet}}'
```

```
sudo docker network ls

docker network inspect airflow_default \
  --format '{{(index .IPAM.Config 0).Subnet}}'
```


Podría devolver:

```
172.17.0.0/16
172.18.0.0/16
```

Abre el archivo indicado por:

```
sudo -u postgres psql -d postgres -c "SHOW hba_file;"
```

Generalmente:

```
sudo nano /etc/postgresql/18/main/pg_hba.conf
```

Agrega al final, ajustando la red si Docker mostró otra:

```
host    etl    postgres    172.17.0.0/16    scram-sha-256
host    etl    postgres    172.18.0.0/16    scram-sha-256
```

Para permitir otras bases y usuarios desde esa red:

```
host    all    all    172.17.0.0/16    scram-sha-256
host    all    all    172.18.0.0/16    scram-sha-256
```

La primera opción es más restrictiva y recomendable para tu caso.

Reinicia PostgreSQL:

```
sudo systemctl restart postgresql
```

## Valida la conexión a la base de datos del host desde el contenedor

En el host validamos que postgres este online:

``` 
pg_isready -h 127.0.0.1 -p 5432 -d etl -U postgres
```

Si todo okay, ingresamos al contenedor de airflow y probamos la conexión

```
sudo docker exec -it airflow-airflow-apiserver-1 bash
pg_isready -h host.docker.internal -p 5432 -d etl -U postgres
```
