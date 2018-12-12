import arcpy

import math
import numpy as np
import numpy.linalg as npla

from datetime import datetime


class MirroredTransformError(Exception):
    pass


class Transform:
    """ A 4-parameter similarity transform.

        The forward transform, (x0, y0) -> (x1, y1) -
        x1 = a0 + a1*x0 - b1*y0
        y1 = b0 + b1*x0 + a1*y0

        The inverse transform, (x1, y1) -> (x0, y0) -
        x0 = a2*(x1 - a0) - b2*(y1 - b0)
        y0 = b2*(x1 - a0) + a2*(y1 - b0)

        where -
        a2 = a1 / (a1**2 + b1**2)
        b2 = -b1 / (a1**2 + b1**2)

        Transform parameters a1 & b1 can be expressed in terms of rotation (r) and scale (k) -
        x1 = a0 + k*cos(r)*x0 - k*sin(r)*y0
        y1 = b0 + k*sin(r)*x0 + k*cos(r)*y0

        where -
        r = atan2(b1, a1)
        k = sqrt(a1**2 + b1**2)

        Transform parameters are saved as a rotation matrix and translation vector -
        R = numpy.array([[a1, -b1], [b1, a1]])
        t = numpy.array([a0, b0])

    """

    def __init__(self, R=None, t=None):
        self.R = R if R is not None else np.identity(2)
        self.t = t if t is not None else np.zeros(2)

    def translation(self):
        # Get the transform displacement (translation)
        x, y = self.t.flat
        return x, y

    def rotation(self):
        # Get the transform rotation in degrees
        a1, b1 = self.R[:, 0].flat
        r = math.degrees(math.atan2(b1, a1))
        return r

    def scale(self):
        # Get the transform scale
        a1, b1 = self.R[:, 0].flat
        k = math.sqrt(a1**2 + b1**2)
        return k

    def forward(self, pt):
        # Forward transform of point coordinates (x, y)
        x, y = (self.t + self.R.dot(pt)).flat
        return x, y

    def inverse(self, pt):
        # Inverse transform of point coordinates (x, y)
        x, y = npla.inv(self.R).dot(np.array(pt) - self.t).flat
        return x, y

    def save(self, outfile):
        # Save transform parameters to a text file
        # A single line should have the comma-separated values for a0,b0,a1,b1
        header = ''
        header += 'Similarity transform paramerters a0, b0, a1, b1\n'
        header += 'Created %s\n' % datetime.now().strftime('%c')
        params = np.hstack((self.t, self.R[:, 0]))
        np.savetxt(outfile, params, header=header)

    def load(self, infile):
        # Load transform parameters from a text file
        a0, b0, a1, b1 = np.loadtxt(infile).flat
        self.R = np.array([[a1, -b1], [b1, a1]])
        self.t = np.array([a0, b0])


def calculate_transform(links, weights=None, rotate=None, scale=None):
    """ Initialize a new local-to-grid transform.
        :param links: list of displacement links
        :param weights: list of weights for corresponding links, defaults to equal weights
        :param rotate: rotation for the transform in degrees, default 0.0
        :param scale: scale factor for the transform, default 1.0
        :return: a Transform object

        Determine transform parameters from one or more links.

        Each link contains coordinates for a name, source (x0, y0) and destination (x1, y1) point.

        ('name', (x0, y0), (x1, y1))

        If the links list contains a single link transform parameters are calculated as -

          a1 = scale * cos(rotate)
          b1 = scale * sin(rotate)
          a0 = x1 - a1*x0 + b1*y0
          b0 = y1 - b1*x0 - a1*y0

        If the links list contains two or more links the method used to obtain
        transform parameters depends on values provided for rotate and scale.

        (1) If both rotate and scale are provided the calculation of the transform parameters
        is the same as the single link case except that a0 & b0 are calculated using the
        centroids for the source and destination links. If a weights list is provided the
        weighted centroid is used instead.

        (2) If only a rotation is provided then scale defaults to 1.0 and parameters are
        calculated as in (1).

        (3) If only a scale is provided then a least squares Rigid transform with
        pre-scaling of the source coordinates is used.

        (4) If neither rotate nor scale are provided then a least squares Conformal transform
        is used to calculate all four transform parameters.

        Final rotation matrix and translation vector are returned as -

        R = numpy.array([[a1, -b1], [b1, a1]])
        t = numpy.array([a0, b0])

        """

    n = len(links)
    assert n > 0
    if weights is None:
        weights = np.ones(n, dtype=np.float64)
    else:
        assert len(weights) == n
        weights = np.array([w[1] for w in weights], dtype=np.float64)

    transform_type = ''

    # array of source and destination points (shape: n, 2)
    src = np.array([p[1] for p in links], dtype=np.float64)
    dst = np.array([p[2] for p in links], dtype=np.float64)

    # centroid coordinates (shape: 2,)
    centroid_src = np.average(src, weights=weights, axis=0)
    centroid_dst = np.average(dst, weights=weights, axis=0)

    if n == 1 or rotate is not None:
        # Single link and multiple link cases (1) and (2)
        if rotate is None:
            rotate = 0.0
        if scale is None:
            scale = 1.0

        transform_type = 'Rotate/Scale/Translate'

        a1 = math.cos(math.radians(rotate)) * scale
        b1 = math.sin(math.radians(rotate)) * scale
        R = np.array([[a1, -b1], [b1, a1]])
        t = centroid_dst - R.dot(centroid_src)

    elif scale is not None:
        # Multiple link case (3)
        transform_type = 'SVD'

        # Center the points.
        src = (src - np.tile(centroid_src, (n, 1)))
        dst = dst - np.tile(centroid_dst, (n, 1))

        H = src.T.dot(np.diag(weights)).dot(dst)
        U, S, Vt = npla.svd(H)
        R = Vt.T.dot(U.T)

        if npla.det(R) < 0:
            raise MirroredTransformError()

        R = R * scale
        t = centroid_dst - R.dot(centroid_src)

    else:
        # Case (4)
        #
        # Calculate translation, rotation and scaling using a least squares Conformal transform.
        #
        # The system Ax = b where -
        #   A is the design matrix created from the source coordinates
        #   x are the transform parameters [a0, b0, a1, b1]'
        #   b is the matrix of observed values [X1, Y1, X2, Y2, ... Xn, Yn]'
        # likely has no solution.
        #
        # We instead find the best-fit parameters for x using a weighted least squares solution -
        #   x = inv(A'*W*A)*A'*W*b

        transform_type = 'Conformal'

        # Design matrix A shape (2*n, 4).
        src = src.dot([[1, 0, 0, 1], [0, -1, 1, 0]]).reshape(n * 2, 2)
        A = np.concatenate((np.tile([[1, 0], [0, 1]], (n, 1)), src), axis=1)

        # Weighting matrix W shape (2*n, 2*n).
        W = np.diag(weights.repeat(2))

        # Observed values b shape (2*n,).
        b = dst.reshape(2 * n)

        if False:
            print('\nA.shape: ' + str(A.shape), '\n', A)
            print('\nW.shape: ' + str(W.shape), '\n', W)
            print('\nb.shape: ' + str(b.shape), '\n', b)

        # Calculate the transform parameters.
        # x = (A.T * W * A).I * A.T * W * b
        x = npla.inv(A.T.dot(W).dot(A)).dot(A.T).dot(W).dot(b)

        a0, b0, a1, b1 = x.flat
        R = np.array([[a1, -b1], [b1, a1]])
        t = np.array([a0, b0])

    xfm = Transform(R, t)
    xfm.transform_type = transform_type

    if False:
        a0, b0 = t.flat
        a1, b1 = R[:, 0].flat
        rotation = xfm.rotation()
        scale = xfm.scale()
        print('\n====================== ' + transform_type + ' Transform parameters ======================\n')
        print('  a0: {0:12.4f}  a1: {1:13.10f}'.format(a0, a1))
        print('  b0: {0:12.4f}  b1: {1:13.10f}'.format(b0, b1))
        print(' rot: {0:12.8f}  sf: {1:13.10f}'.format(rotation, scale))

    return xfm


def calculate_errors(xfm, links):

    # Transform source points and compare to destination points
    names = [s[0] for s in links]
    src = np.array([p[1] for p in links])
    dst = np.array([p[2] for p in links])
    errs = [xfm.forward(p) for p in src] - dst
    errs = np.array([math.sqrt(d[0]**2 + d[1]**2) for d in errs])
    rms = np.sqrt(np.mean(errs**2))

    return zip(names, errs), rms


if __name__ == "__main__":

    from tools.pnezd_link import pnezd_link

    SRC_POINTS = r'data\mcgee-pts-local.txt'
    DST_POINTS = r'data\mcgee-pts-nad83.txt'
    LINKS = r'data\mcgee-links.txt'
    WEIGHTS = r'data\mcgee-weights.txt'
    PARAMS = r'data\mcgee-params.txt'

    from tools.utils import dms_degrees

    pnezd_link(SRC_POINTS, DST_POINTS, LINKS, sigma=0)

    links = []
    weights = []

    with open(LINKS) as f:
        for line in f:
            line = line.strip()
            if line == '' or line.startswith('#'):
                continue

            n = len(links)
            fields = line.split('\t')
            if len(fields) == 4:
                fields.insert(0, '%02d' % (1 + n))      # add a link number

            if len(fields) != 5:
                raise ValueError('Bad links data: %s' % line)

            src = [float(v) for v in fields[1:3]]
            dst = [float(v) for v in fields[3:5]]
            links.append((fields[0], src, dst))

    with open(WEIGHTS) as f:
        for line in f:
            line = line.strip()
            if line == '' or line.startswith('#'):
                continue

            n = len(weights)
            fields = line.split('\t')
            if len(fields) == 1:
                fields.insert(0, '%02d' % (1 + n))      # add a link number

            if len(fields) != 2:
                raise ValueError('Bad weights data: %s' % line)

            weights.append((fields[0], float(fields[1])))

            if weights[n][0] != links[n][0]:
                raise ValueError('Name error: %s' % weights[n][0])

    # xfm = calculate_transform(links[0:1], weights=None, rotate=dms_degrees(-1.0627), scale=0.99990295)
    xfm = calculate_transform(links, weights=weights, rotate=None, scale=None)

    print()
    print('Transform type: ' + xfm.transform_type)

    xfm.save(PARAMS)

    xfm = Transform()
    xfm.load(PARAMS)

    link_errors, rms_error = calculate_errors(xfm, links)

    print
    print('Errors:')
    for name, err in link_errors:
        print('link %s: err=%.4f' % (name, err))

    print()
    print('RMS: %.4f' % rms_error)