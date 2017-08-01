import argparse
import numpy as np
import re

import chainer.links.caffe.caffe_function as caffe
from chainer import serializers

from chainercv.links.model.ssd import Normalize


def rename(name):
    m = re.match(r'conv(\d+)_([123])$', name)
    if m:
        i, j = map(int, m.groups())
        if i >= 6:
            i += 2
        return 'extractor/conv{:d}_{:d}'.format(i, j), True

    m = re.match(r'fc([67])$', name)
    if m:
        return 'extractor/conv{:d}'.format(int(m.group(1))), True

    if name == r'conv4_3_norm':
        return 'extractor/norm4', True

    m = re.match(r'conv4_3_norm_mbox_(loc|conf)$', name)
    if m:
        return 'multibox/{:s}/0'.format(m.group(1)), True

    m = re.match(r'fc7_mbox_(loc|conf)$', name)
    if m:
        return ('multibox/{:s}/1'.format(m.group(1))), True

    m = re.match(r'conv(\d+)_2_mbox_(loc|conf)$', name)
    if m:
        i, type_ = int(m.group(1)), m.group(2)
        if i >= 6:
            return 'multibox/{:s}/{:d}'.format(type_, i - 4), True

    return name, False


class SSDCaffeFunction(caffe.CaffeFunction):

    def __init__(self, model_path):
        print('loading weights from {:s} ... '.format(model_path))
        super(SSDCaffeFunction, self).__init__(model_path)

    def __setattr__(self, name, link):
        new_name, match = rename(name)

        if new_name == 'extractor/conv1_1':
            # BGR -> RGB
            link.W.data[:, ::-1] = link.W.data
            print('{:s} -> {:s} (BGR -> RGB)'.format(name, new_name))
        elif new_name.startswith('multibox/loc/'):
            # xy -> yx
            for data in (link.W.data, link.b.data):
                data = data.reshape((-1, 4) + data.shape[1:])
                data[:, [1, 0, 3, 2]] = data.copy()
            print('{:s} -> {:s} (xy -> yx)'.format(name, new_name))
        elif match:
            print('{:s} -> {:s}'.format(name, new_name))

        super(SSDCaffeFunction, self).__setattr__(new_name, link)

    @caffe._layer('Normalize', None)
    def _setup_normarize(self, layer):
        blobs = layer.blobs
        func = Normalize(caffe._get_num(blobs[0]))
        func.scale.data[:] = np.array(blobs[0].data)
        with self.init_scope():
            setattr(self, layer.name, func)

    @caffe._layer('AnnotatedData', None)
    @caffe._layer('Flatten', None)
    @caffe._layer('MultiBoxLoss', None)
    @caffe._layer('Permute', None)
    @caffe._layer('PriorBox', None)
    def _skip_layer(self, _):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('caffemodel')
    parser.add_argument('output')
    args = parser.parse_args()

    model = SSDCaffeFunction(args.caffemodel)
    serializers.save_npz(args.output, model)


if __name__ == '__main__':
    main()
