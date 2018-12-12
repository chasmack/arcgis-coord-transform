import arcpy
import arcpy.management as mgmt

from tools.transform import Transform


#
# TransformFeatures - transform feature classes
#

def transform_features(input_fc, param_file, direction):

    # X/Y offset from the center of the fc extent for link source points.
    LINK_OFFSET = 1000.0

    xfm = Transform()
    xfm.load(param_file)

    mgmt.RecalculateFeatureClassExtent(input_fc)
    desc = arcpy.Describe(input_fc)
    sr = desc.spatialReference

    ext = desc.extent
    ecx, ecy = (ext.XMin + ext.XMax) / 2.0, (ext.YMin + ext.YMax) / 2.0
    src_ul = arcpy.Point(ecx - LINK_OFFSET, ecy + LINK_OFFSET)
    src_lr = arcpy.Point(ecx + LINK_OFFSET, ecy - LINK_OFFSET)

    links = []
    for src in (src_ul, src_lr):

        if direction == 'Forward':
            dst = arcpy.Point(*xfm.forward((src.X, src.Y)))
        elif direction == 'Inverse':
            dst = arcpy.Point(*xfm.inverse((src.X, src.Y)))
        else:
            arcpy.AddError('Bad direction parameter: "%s"' % direction)
            raise arcpy.ExecuteError

        links.append(arcpy.Polyline(arcpy.Array([src, dst]), sr))

    arcpy.edit.TransformFeatures(input_fc, links, method='SIMILARITY')
    mgmt.RecalculateFeatureClassExtent(input_fc)

    return


class TransformFeatures(object):
    def __init__(self):
        self.label = "Transform Features"
        self.description = "Apply transform to a feature class."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input feature class
        param = arcpy.Parameter(
            displayName='Input Features',
            name='input_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Input'
        )
        params.append(param)

        # Transform parameters
        param = arcpy.Parameter(
            displayName='Transform Parameters',
            name='param_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['txt']
        params.append(param)

        # Direction
        param = arcpy.Parameter(
            displayName='Direction',
            name='direction',
            datatype='GPString',
            parameterType='Required',
            direction='Input'
        )
        param.filter.type = "ValueList"
        param.filter.list = ['Forward', 'Inverse']
        param.value = 'Forward'
        params.append(param)

        # Output feature class
        param = arcpy.Parameter(
            displayName='Output Features',
            name='output_fc',
            datatype='GPFeatureLayer',
            parameterType='Derived',
            direction='Output',
            multiValue=True
        )
        param.parameterDependencies = ['input_fc']
        param.schema.clone = True
        params.append(param)

        return params

    def execute(self, params, messages):
        input_fc = params[0].valueAsText
        param_file = params[1].valueAsText
        direction = params[2].valueAsText

        transform_features(input_fc, param_file, direction)

        params[3].value = input_fc

        return


if __name__ == '__main__':

    input_fc = arcpy.GetParameterAsText(0)
    param_file = arcpy.GetParameterAsText(1)
    direction = arcpy.GetParameterAsText(2)

    transform_features(input_fc, param_file, direction)

    arcpy.SetParameterAsText(3, input_fc)
