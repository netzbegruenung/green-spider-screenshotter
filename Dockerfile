FROM debian:stretch

RUN apt-get update && \
    apt-get install -y python3 python3-pip libfreetype6 libfontconfig wget bzip2 && \
    wget https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2 && \
    tar xjf phantomjs-2.1.1-linux-x86_64.tar.bz2 && \
    rm phantomjs-2.1.1-linux-x86_64.tar.bz2 && \
    mv phantomjs-2.1.1-linux-x86_64 /phantomjs && \
    apt-get remove -y wget bzip2

ADD https://raw.githubusercontent.com/ariya/phantomjs/master/examples/rasterize.js /rasterize.js

WORKDIR /srv

COPY requirements.txt /srv/
RUN pip3 install -r requirements.txt

COPY screenshots.py /srv/


ENTRYPOINT ["python3", "screenshots.py"]
