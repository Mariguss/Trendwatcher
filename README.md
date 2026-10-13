# Trendwatcher

Скачайте зависимости проекта
* Если у вас установлен poetry
```
poetry install
```
* Если вы используете pip
```
pip install -r requirements.txthttps://github.com/Mariguss/Trendwatcher/blob/main/README.md
```
Запустите docker-compose.yaml
```
docker-compose up -d
```
Зайдите на localhost:8081
Введите учетные данные 
```
сервер - pg
логин - user
пароль - password
название бд - db
```

Выполните запрос:
```
CREATE EXTENSION IF NOT EXISTS vector;
```

После в терминале проекта примените миграции:
```
alembic upgrade head
```

Если вы работаете с poetry, выполните команду для импорта зависимостей в файл requirements.txt,

чтобы другие смогли пользоваться своим пакетным менеджером
```
poetry export -f requirements.txt --output requirements.txt --without-hashes
```
