# -*- coding: utf-8 -*-
def classFactory(iface):
    from .plugin import ZoniV2Plugin
    return ZoniV2Plugin(iface)
