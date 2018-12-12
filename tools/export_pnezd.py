import arcpy
import arcpy.management as mgmt

from tools.transform import Transform


#
# ExportPNEZD - Create a PNEZD file from a point feature class
#

def export_pnezd(input_fc, param_file, pnezd_file):

    arcpy.env.addOutputsToMap = False

    if param_file:
        xfm = Transform()
        xfm.load(param_file)

    pts = []
    fields = ('SHAPE@XY', 'ELEVATION', 'NAME', 'DESCRIPTION')
    with arcpy.da.SearchCursor(input_fc, fields) as cur:
        for coords, z, name, desc in cur:
            if param_file:
                coords = xfm.inverse(coords)
                z /= xfm.scale()
            pts.append('%d,%.4f,%.4f,%.4f,%s' % (int(name), *coords[::-1], z, desc))

    with open(pnezd_file, 'w') as f:
        f.write('\n'.join(pts) + '\n')

    return


class ExportPNEZD(object):
    def __init__(self):
        self.label = "Export PNEZD"
        self.description = "Create a PNEZD file from a point feature class."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input point feature class
        param = arcpy.Parameter(
            displayName='Input Point Feature Class',
            name='input_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['Point']
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

        # Output PNEZD File
        param = arcpy.Parameter(
            displayName='Output PNEZD File',
            name='pnezd_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Output'
        )
        param.filter.list = ['txt']
        params.append(param)

        return params

    def execute(self, params, messages):
        input_fc = params[0].valueAsText
        param_file = params[1].valueAsText
        pnezd_file = params[2].valueAsText

        export_pnezd(input_fc, param_file, pnezd_file)

        return


if __name__ == '__main__':
    input_fc = arcpy.GetParameterAsText(0)
    param_file = arcpy.GetParameterAsText(1)
    pnezd_file = arcpy.GetParameterAsText(2)

    export_pnezd(input_fc, param_file, pnezd_file)
