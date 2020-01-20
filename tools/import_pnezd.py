import arcpy
import arcpy.management as mgmt
from datetime import datetime
from dateutil import tz
import os.path

from tools.transform import Transform
from tools.utils import create_points_feature_class


#
# ImportPNEZD - import a PNEZD points file into a points feature class
#

def import_pnezd(pnezd_file, param_file, output_fc):

    POINTS_SYMBOL = 'Flag, Red'
    POINTS_TYPE = 'CAD'

    arcpy.env.addOutputsToMap = False

    pts = []
    with open(pnezd_file) as f:
        for line in f:
            line = line.strip()
            if line == '' or line.startswith('#'):
                continue

            fields = line.split(',', 4)
            if len(fields) == 5:
                pts.append(fields)
            else:
                raise ValueError('Bad source point data: %s' % line)

    if pts:
        if not arcpy.Exists(output_fc):
            create_points_feature_class(output_fc)
        sr = arcpy.Describe(output_fc).spatialReference

        if param_file:
            xfm = Transform()
            xfm.load(param_file)

        pt_time = datetime.now().astimezone(tz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        pt_symbol = POINTS_SYMBOL
        pt_type = POINTS_TYPE
        pt_samples = None

        fields = ('SHAPE@XY', 'ELEVATION', 'TIME', 'NAME', 'DESCRIPTION', 'SYMBOL', 'TYPE', 'SAMPLES')
        cur = arcpy.da.InsertCursor(output_fc, fields)
        for name, n, e, z, desc in pts:
            n, e, z = (float(n) for n in (n, e, z))
            coords = (e, n)
            if param_file:
                coords = xfm.forward(coords)
                z *= xfm.scale()
            cur.insertRow((coords, z, pt_time, name, desc, pt_symbol, pt_type, pt_samples))
        del cur


class ImportPNEZD(object):
    def __init__(self):
        self.label = "Import PNEZD"
        self.description = "Import PNEZD points into a Points feature class."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input PNEZD File
        param = arcpy.Parameter(
            displayName='PNEZD Points',
            name='pnezd_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['txt']
        params.append(param)

        # Transform Parameters (optional)
        param = arcpy.Parameter(
            displayName='Transform Paramaters (Optional)',
            name='param_file',
            datatype='DEFile',
            parameterType='Optional',
            direction='Input'
        )
        param.filter.list = ['txt']
        params.append(param)

        # Output Feature Class
        param = arcpy.Parameter(
            displayName='Output Points Feature Class',
            name='output_fc',
            datatype='GPFeatureLayer',
            parameterType='Optional',
            direction='Output'
        )
        params.append(param)

        return params

    def execute(self, params, messages):
        pnezd_file = params[0].valueAsText
        param_file = params[1].valueAsText
        output_fc = params[2].valueAsText

        import_pnezd(pnezd_file, param_file, output_fc)

        return


if __name__ == '__main__':

    pnezd_file = arcpy.GetParameterAsText(0)
    param_file = arcpy.GetParameterAsText(1)
    output_fc = arcpy.GetParameterAsText(2)

    import_pnezd(pnezd_file, param_file, output_fc)