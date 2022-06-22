docker build -t dotnet:checker ./images/dotnet/
docker build -t python:checker ./images/python/
docker build -t checker:latest ./images/checker/

docker-compose up -d