from importlib import reload

import tools.calculate_transform
import tools.transform_features
import tools.import_pnezd
import tools.export_pnezd
import tools.import_cad
import tools.import_gpx
import tools.export_gpx
import tools.utils

RELOAD = True

if RELOAD:
    reload(tools.calculate_transform)
    reload(tools.transform_features)
    reload(tools.import_pnezd)
    reload(tools.export_pnezd)
    reload(tools.import_cad)
    reload(tools.import_gpx)
    reload(tools.export_gpx)
    reload(tools.utils)

from tools.calculate_transform import CalculateTransform
from tools.transform_features import TransformFeatures
from tools.import_pnezd import ImportPNEZD
from tools.export_pnezd import ExportPNEZD
from tools.import_cad import ImportCAD
from tools.import_gpx import ImportGPX
from tools.export_gpx import ExportGPX
from tools.utils import CreatePointsFC


class Toolbox(object):
    def __init__(self):
        self.label = "Transform Tools"
        self.alias = ""
        self.tools = []
        self.tools += [CalculateTransform, TransformFeatures]
        self.tools += [ImportPNEZD, ExportPNEZD]
        self.tools += [ImportCAD]
        self.tools += [ImportGPX, ExportGPX, CreatePointsFC]