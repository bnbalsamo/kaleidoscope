# kaleidoscope

v0.0.1

[![Build Status](https://travis-ci.org/bnbalsamo/kaleidoscope.svg?branch=master)](https://travis-ci.org/bnbalsamo/kaleidoscope) [![Coverage Status](https://coveralls.io/repos/github/bnbalsamo/kaleidoscope/badge.svg?branch=master)](https://coveralls.io/github/bnbalsamo/kaleidoscope?branch=master)

An [IIIF](http://iiif.io/) image server.

See [here](http://iiif.io/api/image/2.1/) for API details.

# Debug Quickstart
Set environmental variables appropriately
```
./debug.sh
```

# Docker Quickstart
Inject environmental variables appropriately at either buildtime or runtime
```
# docker build . -t kaleidoscope
# docker run -p 5000:80 kaleidoscope --name my_kaleidoscope
```

# Endpoints
## /
### GET
#### Parameters
* None
#### Returns
* JSON: {"status": "Not broken!"}

# Environmental Variables
* None

# Author
Brian Balsamo <brian@brianbalsamo.com>
