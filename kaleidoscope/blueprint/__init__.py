"""
kaleidoscope

an IIIF server.

Implements http://iiif.io/api/image/2.1/
"""
import logging
import re
import json
from hashlib import md5
from io import BytesIO
from math import floor
from os.path import join, isfile

from flask import Blueprint, jsonify, send_file, abort, redirect, \
    make_response
from flask_restful import Resource, Api

from PIL import Image, ImageOps

from .exceptions import ParameterError, IdentifierResolutionError


__author__ = "Brian Balsamo"
__email__ = "brian@brianbalsamo.com"
__version__ = "0.0.2"


BLUEPRINT = Blueprint('kaleidoscope', __name__)


BLUEPRINT.config = {}

API = Api(BLUEPRINT)

log = logging.getLogger(__name__)

format_map = {
    "jpg": "JPEG",
    "tif": "TIFF",
    "png": "PNG",
    "gif": "GIF",
    "jp2": "JPEG2000",
    "pdf": "PDF",
    "webp": "WebP"
}


# https://github.com/loris-imageserver/loris/blob/development/loris/webapp.py#L377
def _import_class(qname):
    '''Imports a class AND returns it (the class, not an instance).
    '''
    module_name = '.'.join(qname.split('.')[:-1])
    class_name = qname.split('.')[-1]
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def parse_identifier_url_component(x):
    if "/" in x:
        abort(404)
    return x


def parse_region_url_component(s):
    # .../full/full/0/default.jpg
    # .../square/full/0/default.jpg
    if s in ("full", "square"):
        return s
    # .../125,15,120,140/full/0/default.jpg
    elif re.match("[0-9]+,[0-9]+,[0-9]+,[0-9]+$", s):
        for x in s.split(","):
            try:
                int(x)
            except ValueError:
                raise ParameterError("Incorrect region paramter")
        return s
    # region=pct:41.6,7.5,40,70
    elif s.startswith("pct:"):
        for x in s[4:].split(","):
            try:
                float(x)
            except ValueError:
                raise ParameterError("Incorrect region paramter")
        return s
    # Error case
    else:
        raise ParameterError("Incorrect region parameter")


def parse_size_url_component(s):
    # /full/full/0/default.jpg
    # /full/max/0/default.jpg
    if s in ("full", "max"):
        # Deprecation Warning
        return "max"
    # .../full/150,/0/default.jpg
    elif s.endswith(","):
        try:
            int(s[:-1])
        except ValueError:
            raise ParameterError("Incorrect size parameter")
        return s
    # .../full/,150/0/default.jpg
    elif s.startswith(","):
        try:
            int(s[1:])
        except ValueError:
            raise ParameterError("Incorrect size parameter")
        return s
    # .../full/pct:50/0/default.jpg
    elif s.startswith("pct:"):
        try:
            float(s[4:])
        except ValueError:
            raise ParameterError("Incorrect size parameter")
        return s
    # .../full/225,100/0/default.jpg
    # .../full/!225,100/0/default.jpg
    elif re.match("^(\!)?[0-9]+,[0-9]+$", s):
        if s.startswith("!"):
            c = s[1:]
        else:
            c = s
        for x in c.split(","):
            try:
                int(x)
            except ValueError:
                raise ParameterError("Incorrect size parameter")
        return s
    # Error case
    else:
        raise ParameterError("Incorrect size parameter")


def parse_rotation_url_component(s):
    # .../full/full/0/default.jpg
    # .../full/full/!0/default.jpg
    if s.startswith("!"):
        if len(s) < 2:
            raise ParameterError("Incorrect rotation paramter")
        c = s[1:]
    else:
        c = s
    try:
        assert(0 <= float(c) <= 360)
        return s
    # Error case
    except (ValueError, AssertionError):
        raise ParameterError("Incorrect rotation parameter")


def parse_quality_url_component(x):
    if x in ("color", "gray", "bitonal", "default"):
        return x
    else:
        raise ParameterError("Incorrect quality parameter")


def parse_format_url_component(x):
    if x in format_map:
        return x
    else:
        raise ParameterError("Incorrect format paramter")


class DefaultResolver:
    def __init__(self, config):
        self.root = config['IMG_ROOT']

    def resolve_identifier(self, x):
        path = join(self.root, x)
        if not isfile(path):
            raise IdentifierResolutionError("No image matching that identifier found!")
        return Image.open(path)


def perform_crop(img, region_url_component):
    o_width, o_height = img.size
    if region_url_component == "full":
        return img
    elif region_url_component == "square":
        if o_width == o_height:
            return img
        short_side = min(o_height, o_width)
        img = img.crop((0, 0, short_side, short_side))
    elif region_url_component.startswith("pct:"):
        scalars = [float(x)/100 for x in region_url_component[4:].split(",")]
        dimensions = [
            floor(scalars[0]*o_width),
            floor(scalars[1]*o_height),
            floor(scalars[2]*o_width),
            floor(scalars[3]*o_height)
        ]
        dimensions[2] = dimensions[2] + dimensions[0]
        dimensions[3] = dimensions[3] + dimensions[1]
        img = img.crop(tuple(dimensions))
    else:
        dimensions = [int(x) for x in region_url_component.split(",")]
        dimensions[2] = dimensions[2] + dimensions[0]
        dimensions[3] = dimensions[3] + dimensions[1]
        img = img.crop(tuple(dimensions))
    return img


def perform_scale(img, scale_url_component):
    o_width, o_height = img.size
    if scale_url_component is "max":
        return img
    elif scale_url_component.endswith(","):
        width = int(scale_url_component[:-1])
        ratio = o_width/width
        height = o_height / ratio
        return img.resize(
            (floor(width), floor(height)),
            resample=Image.ANTIALIAS
        )
    elif scale_url_component.startswith(","):
        height = int(scale_url_component[1:])
        ratio = o_height/height
        width = o_width / ratio
        return img.resize(
            (floor(width), floor(height)),
            resample=Image.ANTIALIAS
        )
    elif scale_url_component.startswith("pct:"):
        scalar = int(scale_url_component[4:])/100
        return img.resize(
            (floor(o_width*scalar),
             floor(o_height*scalar)),
            resample=Image.ANTIALIAS
        )
    elif scale_url_component.startswith("!"):
        w_ratio = o_width/int(scale_url_component[1:].split(",")[0])
        h_ratio = o_height/int(scale_url_component[1:].split(",")[1])
        if w_ratio > h_ratio:
            return img.resize(
                (floor(o_width/w_ratio), floor(o_height/w_ratio)),
                resample=Image.ANTIALIAS
            )
        else:
            return img.resize(
                (floor(o_width/h_ratio), floor(o_height/h_ratio)),
                resample=Image.ANTIALIAS
            )
    else:
        return img.resize(
            (int(scale_url_component.split(",")[0]),
             int(scale_url_component.split(",")[1])),
            resample=Image.ANTIALIAS
        )


def perform_rotate(img, rotation_url_component):
    if rotation_url_component.startswith("!"):
        img = ImageOps.mirror(img)
        rotation_url_component = rotation_url_component[1:]
    img = img.rotate(360-float(rotation_url_component), expand=True)
    return img


def perform_quality(img, quality_url_component):
    if quality_url_component in ("default", "color"):
        return img
    elif quality_url_component == "gray":
        img = img.convert('LA')
        img = img.convert('RGB')
        return img
    elif quality_url_component == "bitonal":
        img = img.convert('1', dither=None)
        img = img.convert('RGB')
        return img
    else:
        raise AssertionError("We should never get here")


def generate_image_info(identifier):
    parsed_identifier = parse_identifier_url_component(identifier)
    img = BLUEPRINT.config['resolver'].resolve_identifier(parsed_identifier)
    result_dict = {}
    result_dict['@context'] = 'http://iiif.io/api/image/2/context.json'
    result_dict['@id'] = "{}/{}".format(BLUEPRINT.config['API_URL'], identifier)
    result_dict['protocol'] = 'http://iiif.io/api/image'
    w, h = img.size
    result_dict['width'] = w
    result_dict['height'] = h
    result_dict['profile'] = ['http://iiif.io/api/image/2/level2.json']
    result_dict['profile'].append(
        {
            "formats": ["gif", "jpg", "png", "tif"],
            "qualities": ["color", "gray", "bitonal"],
            "supports": [
                "baseUriRedirect", "cors", "jsonldMediaType", "mirroring",
                "regionByPct", "regionByPx", "regionSquare",
                "rotationArbitrary", "sizeByConfinedWh", "sizeByDistoredWh",
                "sizeByH", "sizeByPct", "sizeByW", "sizeByWh"
            ]
        }
    )

    if BLUEPRINT.config.get('ATTRIBUTION_STR'):
        result_dict['attribution'] = BLUEPRINT.config['ATTRIBUTION_STR']
    if BLUEPRINT.config.get('LICENSE_LINK'):
        result_dict['license'] = BLUEPRINT.config['LICENSE_LINK']
    if BLUEPRINT.config.get('LOGO_LINK'):
        result_dict['logo'] = BLUEPRINT.config['LOGO_LINK']

    return result_dict


class Root(Resource):
    def get(self):
        return {"Status": "Not broken!"}


class Version(Resource):
    def get(self):
        return {"version": __version__}


class ImageRequestURI(Resource):
    def get(self, identifier, region, size, rotation, quality, format):
        try:
            parsed_args = {}
            parsed_args['identifier'] = parse_identifier_url_component(identifier)
            parsed_args['region'] = parse_region_url_component(region)
            parsed_args['size'] = parse_size_url_component(size)
            parsed_args['rotation'] = parse_rotation_url_component(rotation)
            parsed_args['quality'] = parse_quality_url_component(quality)
            parsed_args['format'] = parse_format_url_component(format)
        except ParameterError:
            abort(400)

        try:
            image = BLUEPRINT.config['resolver'].resolve_identifier(identifier)
        except IdentifierResolutionError:
            abort(404)

        image = perform_crop(image, parsed_args['region'])
        image = perform_scale(image, parsed_args['size'])
        image = perform_rotate(image, parsed_args['rotation'])
        image = perform_quality(image, parsed_args['quality'])

        final_image = BytesIO()
        image.save(final_image, format_map[parsed_args['format']])
        final_image.seek(0)
        return send_file(
            final_image,
            attachment_filename="{}.{}".format(
                md5(json.dumps(parsed_args).encode()).hexdigest(),
                format)
        )


class ImageInformationRequestURI(Resource):
    def get(self, identifier):
        result_dict = generate_image_info(identifier)
        response = make_response(
            jsonify(result_dict)
        )
        response.mimetype = "application/ld+json"
        response.headers['access-control-allow-origin'] = "*"
        return response


class IdentifierCatch(Resource):
    def get(self, identifier):
        return redirect(API.url_for(ImageInformationRequestURI, identifier=identifier))


@BLUEPRINT.record
def handle_configs(setup_state):
    app = setup_state.app
    BLUEPRINT.config.update(app.config)
    if BLUEPRINT.config.get('DEFER_CONFIG'):
        log.debug("DEFER_CONFIG set, skipping configuration")
        return

    if BLUEPRINT.config.get('RESOLVER'):
        # Import and use a custom resolver class
        BLUEPRINT.config['resolver'] = _import_class(
            BLUEPRINT.config['RESOLVER'])(BLUEPRINT.config)
    else:
        # Use the default resolver
        BLUEPRINT.config['resolver'] = DefaultResolver(BLUEPRINT.config)

    if BLUEPRINT.config.get("VERBOSITY"):
        log.debug("Setting verbosity to {}".format(str(BLUEPRINT.config['VERBOSITY'])))
        logging.basicConfig(level=BLUEPRINT.config['VERBOSITY'])
    else:
        log.debug("No verbosity option set, defaulting to WARN")
        logging.basicConfig(level="WARN")


API.add_resource(Root, "/")
API.add_resource(Version, "/version")
# {scheme}://{server}{/prefix}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}
API.add_resource(ImageRequestURI,
                 "/<path:identifier>/<region>/<size>/<rotation>/<quality>.<format>")
# {scheme}://{server}{/prefix}/{identifier}/info.json
API.add_resource(ImageInformationRequestURI,
                 "/<path:identifier>/info.json")
API.add_resource(IdentifierCatch,
                 "/<path:identifier>")
