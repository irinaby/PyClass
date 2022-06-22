FROM python:3

RUN pip install docker

WORKDIR /usr/src

ADD src/* ./

EXPOSE 3356

CMD ["python", "./main.py"]

