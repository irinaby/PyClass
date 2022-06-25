docker build -t checker:latest ./images/checker/
docker build -t dotnet:builder ./images/dotnet.builder/
docker build -t dotnet:runtime ./images/dotnet.runtime/
docker build -t python:checker ./images/python/
docker build -t gcc:builder ./images/gcc/

docker-compose up -d