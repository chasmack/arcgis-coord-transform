import arcpy
import arcpy.management as mgmt

from tools.transform import Transform


#
# ImportCAD - import CAD features transforming the output feature class
#

def import_cad(input_fc, param_file, output_fc):

    # Copy the cad features
    mgmt.CopyFeatures(input_fc, output_fc)

    if param_file:

        # X/Y offset from the center of the fc extent for link source points.
        LINK_OFFSET = 1000.0

        xfm = Transform()
        xfm.load(param_file)

        desc = arcpy.Describe(output_fc)
        ext = desc.extent
        ctr_x, ctr_y = (ext.XMin + ext.XMax) / 2.0, (ext.YMin + ext.YMax) / 2.0
        src_ul = arcpy.Point(ctr_x - LINK_OFFSET, ctr_y + LINK_OFFSET)
        src_lr = arcpy.Point(ctr_x + LINK_OFFSET, ctr_y - LINK_OFFSET)

        links = []
        sr = desc.spatialReference
        for src in (src_ul, src_lr):
            dst = arcpy.Point(*xfm.forward((src.X, src.Y)))
            links.append(arcpy.Polyline(arcpy.Array([src, dst]), sr))

        arcpy.edit.TransformFeatures(output_fc, links, method='SIMILARITY')
        mgmt.RecalculateFeatureClassExtent(output_fc)

    return


class ImportCAD(object):
    def __init__(self):
        self.label = "Import CAD"
        self.description = "Import CAD features optionally applying a transform."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input feature class
        param = arcpy.Parameter(
            displayName='Input CAD Features',
            name='input_fc',
            datatype='DEFeatureClass',
            parameterType='Required',
            direction='Input'
        )
        params.append(param)

        # Transform parameters
        param = arcpy.Parameter(
            displayName='Transform Parameters (Optional)',
            name='param_file',
            datatype='DEFile',
            parameterType='Optional',
            direction='Input'
        )
        param.filter.list = ['txt']
        params.append(param)

        # Output feature class
        param = arcpy.Parameter(
            displayName='Output Feature Class',
            name='output_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Output'
        )
        params.append(param)

        return params

    def execute(self, params, messages):
        input_fc = params[0].valueAsText
        param_file = params[1].valueAsText
        output_fc = params[2].valueAsText

        import_cad(input_fc, param_file, output_fc)

        return


if __name__ == '__main__':

    input_fc = arcpy.GetParameterAsText(0)
    param_file = arcpy.GetParameterAsText(1)
    output_fc = arcpy.GetParameterAsText(2)

    import_cad(input_fc, param_file, output_fc)
