
Dockerfile for a website screenshot tool based on PhantomJS.

Thanks to https://github.com/ubermuda/docker-screenshot for the inspiration!

## Usage

```
docker run --rm -v $PWD:/srv netbegruenung/green-spider-screenshotter "http://www.google.com/" google.com.png "1500px*1500px"
```
