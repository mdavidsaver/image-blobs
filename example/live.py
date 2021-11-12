#!/usr/bin/env python

import os
import logging
import threading
import signal
import time
import enum
import faulthandler

import numpy as np

os.environ.pop('DISPLAY') # we want headless operation
import matplotlib
matplotlib.use('agg')

import image_blobs

from p4p.nt import NTNDArray, NTScalar, NTTable, NTEnum
from p4p.client.thread import Context
from p4p.server.thread import SharedPV
from p4p.server import Server

try:
    import setproctitle
except ImportError:
    pass
else:
    setproctitle.setproctitle("liveblobs") # trigger stack traces with 'pkill -HUP liveblobs'

_log = logging.getLogger(__name__)

class ImageMode(enum.IntEnum):
    Sum = 0
    Red = 1
    Green = 2
    Blue = 3

def getargs():
    from argparse import ArgumentParser
    P = ArgumentParser()
    P.add_argument('input', help='Input NTNDArray PV name')
    P.add_argument('output', help='Output PV name prefix')
    return P

class App:
    def __init__(self, args):
        self.args = args
        self.bgLvl = 200
        self.imode = 0

    def main(self):
        cli = Context()

        pvs = {}
        # table of detected "features"
        self.features = pvs[args.output+'features'] = SharedPV(nt=NTTable(columns=[
            ('X', 'd'),
            ('Y', 'd'),
            ('W', 'd'),
            ('H', 'd'),
            ('idx', 'd'),
        ]), initial=[])
        # output image (example)
        self.imgOut = pvs[args.output+'img'] = SharedPV(nt=NTNDArray(), initial=np.zeros((0,0), dtype='u1'))
        # display execution time
        self.execTime = pvs[args.output+'etime'] = SharedPV(nt=NTScalar('d',  display=True), initial={
            'value':0.0,
            'display.units':'s',
        })
        # background threshold level
        bg = pvs[args.output+'bg'] = SharedPV(nt=NTScalar('I',  display=True), initial={
            'value':self.bgLvl,
            'display.units':'px',
        })
        @bg.put
        def set_bg(pv, op):
            self.bgLvl = max(1, int(op.value()))
            pv.post(self.bgLvl)
            op.done()
        # image flattening mode
        imode = pvs[args.output+'imode'] = SharedPV(nt=NTEnum(), initial={
            'choices':[e.name for e in ImageMode]})
        @imode.put
        def set_imode(pv, op):
            self.imode = ImageMode(op.value())
            pv.post(self.imode)
            op.done()

        # separately publish info of largest feature
        self.X = pvs[args.output+'x'] = SharedPV(nt=NTScalar('d'), initial=0.0)
        self.Y = pvs[args.output+'y'] = SharedPV(nt=NTScalar('d'), initial=0.0)
        self.W = pvs[args.output+'w'] = SharedPV(nt=NTScalar('d'), initial=0.0)
        self.H = pvs[args.output+'h'] = SharedPV(nt=NTScalar('d'), initial=0.0)

        print("Output PVs", list(pvs.keys()))

        # subscribe to input image PV and run local server
        with cli.monitor(self.args.input, self.on_image, request='record[pipeline=true,queueSize=2]'), Server(providers=[pvs]):
            # park while work happens in other tasks
            done = threading.Event()
            signal.signal(signal.SIGINT, lambda x,y:done.set())
            done.wait()

    def on_image(self, img):
        '''New image arrives, interesting stuff happens here
        '''
        T0 = time.monotonic()
        _log.info('on_image %s bg=%d imode=%s', img.shape, self.bgLvl, self.imode)

        if img.ndim==3 and img.shape[2]==3:
            if self.imode==ImageMode.Sum:
                img = img.astype('u2').sum(axis=2)/3
            else:
                img = img[:,:,self.imode-1]
        assert img.ndim==2, img.shape

        try:
            # do expensive processing in worker thread
            features = image_blobs.find_blobs(img, limit=3, bg=self.bgLvl)

            for F in features[:1]: # at most one iteration
                self.X.post(F['X'])
                self.Y.post(F['Y'])
                self.W.post(F['W'])
                self.H.post(F['H'])

            self.features.post(features)

            img = show_features(img, features)

            self.imgOut.post(img)
        except:
            _log.exception("oops")

        self.execTime.post(time.monotonic()-T0)


def show_features(img, Fs, title='', sigma=1.0):
    '''Show image superimposed with blob position and size
    '''
    import matplotlib.pyplot as plt
    plt.clf()
    fig = plt.gcf()
    plt.imshow(img)
    plt.errorbar(Fs['X'], Fs['Y'], xerr=Fs['W']*0.5*sigma, yerr=Fs['H']*0.5*sigma, fmt='b+')
    plt.title(title)

    fig.canvas.draw()
    W, H = fig.canvas.get_width_height()
    pix = fig.canvas.tostring_rgb()
    pix = np.frombuffer(pix, dtype='u1').reshape((H,W,3))

    return pix

if __name__=='__main__':
    faulthandler.register(signal.SIGHUP)
    logging.basicConfig(level=logging.INFO)
    args = getargs().parse_args()
    App(args).main()
