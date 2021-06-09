FROM kenhv/kensurbot:debian

RUN set -ex \
    && git clone -b master https://github.com/uhwot/KensurBot /root/userbot \
    && chmod 777 /root/userbot

WORKDIR /root/userbot/

CMD ["python3", "-m", "userbot"]
