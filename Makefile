

build:
	docker build -t screenshotter .

run:
	docker run --rm -ti --name screenshotter \
		-v $(shell pwd)/secrets:/secrets \
		screenshotter:latest
