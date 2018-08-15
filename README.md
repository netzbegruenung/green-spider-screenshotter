[![Docker Repository on Quay](https://quay.io/repository/netzbegruenung/green-spider-screenshotter/status "Docker Repository on Quay")](https://quay.io/repository/netzbegruenung/green-spider-screenshotter)

# Green Spider Screenshotter

Part of https://github.com/netzbegruenung/green-spider

Creates screenshots of web URLs in various resolutions. Uploads the resulting images
to a Google Cloud Storage bucket, stores metadata in Google Cloud Datastore.

## Usage

Place the Google Cloud service account JSON file into `secrets/service-account.json`.

Then execute this:

```nohighlight
make
make run
```

or

```
docker run --rm -ti \
	-v $(pwd)/secrets:/secrets \
	quay.io/netzbegruenung/green-spider-screenshotter
```