"""
Custom Request/Response Transformation Plugin for Edge Crew v3.0 API Gateway
"""

import json
import re
from typing import Dict, List, Optional, Any

VERSION = "1.0.0"
PRIORITY = 800


class Config:
    def __init__(self):
        self.request_headers_add = {}
        self.request_headers_remove = []
        self.request_headers_rename = {}
        self.response_headers_add = {}
        self.response_headers_remove = []
        self.response_headers_rename = {}
        self.path_prefix_remove = None
        self.path_prefix_add = None
        self.query_params_add = {}
        self.query_params_remove = []


class RequestTransformer:
    def __init__(self, config: Config):
        self.config = config

    def transform_headers(self, kong):
        for header, value in self.config.request_headers_add.items():
            kong.service.request.set_header(header, value)
        for header in self.config.request_headers_remove:
            kong.service.request.clear_header(header)
        for old_name, new_name in self.config.request_headers_rename.items():
            value = kong.request.get_header(old_name)
            if value:
                kong.service.request.set_header(new_name, value)
                kong.service.request.clear_header(old_name)

    def transform_path(self, kong):
        path = kong.request.get_path()
        if self.config.path_prefix_remove and path.startswith(self.config.path_prefix_remove):
            path = path[len(self.config.path_prefix_remove):]
        if self.config.path_prefix_add:
            path = self.config.path_prefix_add + path
        kong.service.request.set_path(path)

    def transform_query(self, kong):
        for param, value in self.config.query_params_add.items():
            kong.service.request.set_query(param, value)
        for param in self.config.query_params_remove:
            kong.service.request.clear_query_arg(param)


class ResponseTransformer:
    def __init__(self, config: Config):
        self.config = config

    def transform_headers(self, kong):
        for header, value in self.config.response_headers_add.items():
            kong.response.set_header(header, value)
        for header in self.config.response_headers_remove:
            kong.response.clear_header(header)


class Plugin:
    def __init__(self, config: Dict):
        self.config = Config()
        for key, value in config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.request_transformer = RequestTransformer(self.config)
        self.response_transformer = ResponseTransformer(self.config)

    def access(self, kong):
        self.request_transformer.transform_headers(kong)
        self.request_transformer.transform_path(kong)
        self.request_transformer.transform_query(kong)

    def header_filter(self, kong):
        self.response_transformer.transform_headers(kong)


def access(kong):
    config = kong.configuration
    plugin = Plugin(config)
    return plugin.access(kong)


def header_filter(kong):
    config = kong.configuration
    plugin = Plugin(config)
    return plugin.header_filter(kong)


Schema = {
    "name": "edge-transform",
    "fields": [
        {"request_headers_add": {"type": "map", "default": {}}},
        {"request_headers_remove": {"type": "array", "default": []}},
        {"request_headers_rename": {"type": "map", "default": {}}},
        {"response_headers_add": {"type": "map", "default": {}}},
        {"response_headers_remove": {"type": "array", "default": []}},
        {"response_headers_rename": {"type": "map", "default": {}}},
        {"path_prefix_remove": {"type": "string"}},
        {"path_prefix_add": {"type": "string"}},
        {"query_params_add": {"type": "map", "default": {}}},
        {"query_params_remove": {"type": "array", "default": []}},
    ],
}
