import arcpy
import os.path
import xml.etree.ElementTree as etree
import tools.transform as transform
import tools.utils as utils

# from importlib import reload
# reload(transform)

DEFAULTS_FILE = r'transform\Transform.xml'

#
# CalculateTransform - calculate transform parameters from source and target points
#

def calculate_transform(source_fc, target_fc, rotate, scale, param_file, links_list):

    # Check source and target are using the same coordinate system
    source_sr = arcpy.Describe(source_fc).spatialReference
    target_sr = arcpy.Describe(target_fc).spatialReference
    if source_sr.factoryCode != target_sr.factoryCode:
        arcpy.AddError('Source and Target feature classes using different coordinate systems.')
        exit(-1)

    # Read the source and target points
    with arcpy.da.SearchCursor(source_fc, ['NAME', 'SHAPE@XY']) as cur:
        source_pts = dict(cur)
    with arcpy.da.SearchCursor(target_fc, ['NAME', 'SHAPE@XY']) as cur:
        target_pts = dict(cur)

    links = []
    weights = []
    for name, source, target, weight in links_list:
        if source not in source_pts:
            arcpy.AddError('Source point not found: link=%s name=%s' % (name, source))
            exit(-1)
        if target not in target_pts:
            arcpy.AddError('Target point not found: link=%s name=%s' % (name, target))
            exit(-1)
        try:
            weight = float(weight)
        except ValueError:
            arcpy.AddError('Bad weight value: link=%s weight=%s' % (name, weight))
            exit(-1)
        links.append([name, source_pts[source], target_pts[target]])
        weights.append([name, weight])

    # Rotation can be expressed as signed decimal degrees or signed DMS
    if rotate is not None:
        try:
            dms = rotate.split()
            if len(dms) == 3:
                deg, min, sec = dms
                dec = utils.dms_degrees([int(deg), int(min), float(sec)])
            elif len(dms) == 2:
                deg, min = dms
                dec = utils.dms_degrees([int(deg), float(min)])
            elif len(dms) == 1:
                dec = float(dms)
            else:
                raise ValueError
            rotate = dec
        except ValueError:
            arcpy.AddError('Bad rotation value: %s' % rotate)
            exit(-1)

    if scale is not None:
        try:
            scale = float(scale)
        except ValueError:
            arcpy.AddError('Bad scale value: %s' % scale)
            exit(-1)

    # arcpy.AddMessage('links: %s' % links)
    # arcpy.AddMessage('weights: %s' % weights)
    # arcpy.AddMessage('rotate: %s' % rotate)
    # arcpy.AddMessage('scale: %s' % scale)

    xfm = transform.calculate_transform(links, weights=weights, rotate=rotate, scale=scale)
    xfm.save(param_file)

    arcpy.AddMessage('Number of links: %d' % len(links))
    arcpy.AddMessage('Transform type: %s' % xfm.transform_type)

    if len(links) > 1:

        link_errors, rms_error = transform.calculate_errors(xfm, links)

        arcpy.AddMessage('Errors:')
        for name, err in link_errors:
            arcpy.AddMessage('link %s: err=%.4f' % (name, err))

        arcpy.AddMessage('RMS error: %.4f' % rms_error)

    return


class CalculateTransform(object):
    def __init__(self):
        self.label = "Calculate Transform"
        self.description = "Calculate parameters for a similarity transform."
        self.category = None
        self.canRunInBackground = False

    def getParameterInfo(self):

        # Get initial values for the input parameters
        aprx_path = os.path.dirname(arcpy.mp.ArcGISProject('current').filePath)
        defaults_file = os.path.join(aprx_path, DEFAULTS_FILE)
        defaults = {}
        if os.path.isfile(defaults_file):
            xml = etree.parse(defaults_file).getroot()
            for tag in ('source', 'target', 'rotation', 'scale', 'output'):
                elem = xml.find(tag)
                if elem is not None:
                    defaults[tag] = elem.text
            links = []
            for link in xml.findall('link'):
                vals = []
                for tag in ('name', 'source', 'target', 'weight'):
                    elem = link.find(tag)
                    vals.append(elem.text if elem is not None else '')
                links.append(vals)
            if links:
                defaults['links'] = links

        params = []

        # Source points feature layer
        param = arcpy.Parameter(
            displayName='Source Points',
            name='src_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['POINT']
        if 'source' in defaults:
            param.value = defaults['source']
        params.append(param)

        # Destination points feature layer
        param = arcpy.Parameter(
            displayName='Target Points',
            name='target_fc',
            datatype='GPFeatureLayer',
            parameterType='Required',
            direction='Input'
        )
        param.filter.list = ['POINT']
        if 'target' in defaults:
            param.value = defaults['target']
        params.append(param)

        # Optional rotation
        param = arcpy.Parameter(
            displayName='Rotation',
            name='rotate',
            datatype='GPString',
            parameterType='Optional',
            direction='Input'
        )
        if 'rotation' in defaults:
            param.value = defaults['rotation']
        params.append(param)

        # Optional scale
        param = arcpy.Parameter(
            displayName='Scale',
            name='scale',
            datatype='GPString',
            parameterType='Optional',
            direction='Input'
        )
        if 'scale' in defaults:
            param.value = defaults['scale']
        params.append(param)

        # Output parameters file
        param = arcpy.Parameter(
            displayName='Ouptut Transform Parameter File',
            name='param_file',
            datatype='DEFile',
            parameterType='Required',
            direction='Output'
        )
        param.filter.list = ['txt']
        if 'output' in defaults:
            param.value = defaults['output']
        params.append(param)

        # Sourec-target links value table
        param = arcpy.Parameter(
            displayName='Links',
            name='links_list',
            datatype='GPValueTable',
            parameterType='Required',
            direction='Input'
        )
        param.columns = [
            ['GPString', 'Name'],
            ['GPString', 'Source Point'],
            ['GPString', 'Target Point'],
            ['GPString', 'Weight']
        ]
        if 'links' in defaults:
            param.value = defaults['links']
        params.append(param)

        return params

    def execute(self, params, messages):
        source_fc = params[0].valueAsText
        target_fc = params[1].valueAsText
        rotate = params[2].valueAsText
        scale = params[3].valueAsText
        param_file = params[4].valueAsText
        links_list = params[5].values

        calculate_transform(source_fc, target_fc, rotate, scale, param_file, links_list)

        return


if __name__ == '__main__':

    source_fc = arcpy.GetParameterAsText(0)
    target_fc = arcpy.GetParameterAsText(1)
    rotate = arcpy.GetParameterAsText(2)
    scale = arcpy.GetParameterAsText(3)
    param_file = arcpy.GetParameterAsText(4)
    links_list = arcpy.GetParameter(5)

    calculate_transform(source_fc, target_fc, rotate, scale, param_file, links_list)