"""
	Author: Fabian Brix

	inspired by
	http://minds.jacobs-university.de/mantas
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.linalg as lg 
import inspect
import time
import pickle

class ESN:
    """
        definitions:
        N - number of points in training set
        T - time interval of input
        Nu - size of the input signal
        Nx- size of the reservoir

        training tips:
        -keep reservoir size small for selection of hyperparams
    """	
    def __init__(self, data, split_ind, initN):
        self._dates = data[0]
        self._traindates =  self._dates[initN+1:split_ind+1]
        data = data[1]
        self._data = data
        self._N = split_ind
        self._train = data[initN:split_ind+1]
        self._test = data[split_ind:]
        self._Ytrain = np.zeros(len(self._traindates))

        try:
            self._Nu = self._data.shape[1]
        except IndexError:
            self._Nu = 1

        self._initN = initN
        # one element of prediction granularity less than actually available data
        #self._N = 1825 # 5 years worth of daily data?
        #self._initN = 365 # 1 year worth of initialization
        self._y = 0
        # select v for concrete reservoir using validation, just rerun Y=W_out.bUX for different v
        self._nu = 1E-8
        self._mu = 0.3

    def init_reservoir(self, Nx):
        # "the bigger the size of the space of reservoir signals x(n), the easier it is to find a linear combination of the signals to approximate y_target(n)"
        # N > 1+Nu+Nx should hold true
        self._Nx = Nx
        self._Ny = 1

    def init_Weights(self, squared = False):
        np.random.seed(42)

        self._Win = np.random.uniform(-1,1,size=(self._Nx,self._Ny))

        # Internal connection - to speed up computation make matrix sparse (set random entries to zero)
        self._W = np.random.uniform(-1,1,size=(self._Nx, self._Nx))
        it = np.nditer(self._W, flags=['multi_index'])
        while not it.finished:
            if np.random.rand(1)[0] < 0.95:
                self._W[it.multi_index] = 0.0
            it.iternext()
        print np.max(self._W)
        print np.min(self._W)

        # Compute W's eigenvalues
        eigValuesVectors = lg.eig(self._W)
        eigValues = eigValuesVectors[0]

        # Compute spectral radius = max abs eigenvalue
        # the spectral radius determines how fast the influence of an input dies out in a reservoir with time and how stable reservoir activations are
        # => the spectral radius should be greater in tasks requiring longer memory of the input
        
        #rhoW = np.max(np.abs(eigValues))
        rhoW = np.max(eigValues)

        # Normalize random weight matrix by spectral radius
        self._W/=rhoW

        # Rescale matrix - Parameter to be TUNED
        rescale = 0.8
        self._W*=rescale

        self._Wout = np.zeros((self._Ny+self._Nx, 1))


    def init_training(self):
        self._x = np.zeros((self._Nx,1))
        """
            Design matrix [1,U,X]
            keep N-initN time-steps in the design matrix, discard the initial initN steps
        """

        self._Yt = self._data[self._initN+1:self._N+1] 

    def LMS_update(self, t, y, state):
        stab = 2.0/np.power(np.linalg.norm(state),2)
        if self._mu >= stab:
            self._mu = stab/2.0

        err = self._data[t+1] - y

        self._Wout = self._Wout + self._mu * np.dot(state,err)

    def run_training(self, runs = False):
        self._runs = 0
        niter = 0
        # t < self._N
        self._y = self._data[0]
        for t in xrange(self._N):

            # white noise on x
            self._x = np.tanh(np.dot(self._Win, self._y)+np.dot(self._W,self._x)+np.random.normal(0, 0.0001))

            state = np.vstack((self._y,self._x))
            
            if t >= self._initN:
                self._y = np.dot(state.T, self._Wout)
                self._Ytrain[t-self._initN] = self._y
                if niter % 100 == 0:
                    print 'iteration: ', niter
                    print 'y', self._y
                    yt = self._data[t+1]
                    print 'y target ', yt

                self.LMS_update(t, self._y, state)
                niter += 1

        if isinstance(self._runs, int) and self._runs > 1:
            # Depending on online or batch collect bUX or 
            #self.init_W()
            self._runcnt += 1
            if teacher_force: 
                self._runs = np.vstack((self._runcnt, self._y))
            else:
                # TODO: check this - how to store runs
                self._runs = np.vstack((self._runcnt, self._bUX))
            self.run_training(*params) 

    def custom_training(self, runs = False):
    #   params = self.run_training.func_code.co_varnames[1:self.run_training.func_code.co_argcount]
        self.init_training()

        self.init_Weights()

        self._alpha = 0.3

        self.run_training(runs)

        self.train_err()
        # TODO print error, prompt save params? use pickle for dumping

    # specify prediction horizon when calling function
    def generative_run(self, horizon):
        Y = np.zeros((self._Ny,horizon))
        # use last output as input to make first prediction
        print self._data[self._N-1]
        for t in range(horizon):
            print 't ', t

            xlast = self._x
            self._y+=1
            xnext = np.tanh(np.dot(self._Win, self._y)+np.dot(self._W, xlast)+np.random.normal(0, 0.0001))
            self._x = (1-self._alpha)*xlast + self._alpha*xnext

            out = np.vstack((self._y, self._x))
            self._y = np.dot(out.T, self._Wout)

            u = self._data[self._N+t]
            print 'u ', u
            print 'y ', self._y
            Y[:,t] = self._y
            # use prediction as input to the network

        self.test_err(Y, horizon)
        return Y

    def train_err(self):
        mse = np.sum( np.square( self._train[1:] - self._Ytrain[:] ) ) / (self._N-self._initN)
        print 'training mse: ', mse

    def test_err(self, Y, horizon):
		mse = np.sum( np.square( self._data[self._N:self._N+horizon] - Y[0,0:horizon] ) ) / horizon 
		print 'test mse: ', mse

    def plot_training(self, title, ylabel):
        print 'plotting training'
        fmt = mdates.DateFormatter('%d-%m-%Y')
        #loc = mdates.WeekdayLocator(byweekday=mdates.Monday)
        months = self._traindates

        train = self._data[self._initN+1:self._N+1] 

        plt.figure(10).clear()
        plt.plot_date(x=months, y=self._Ytrain, fmt="-", color='blue')
        plt.plot_date(x=months, y=train, fmt="-", color='green')

        plt.title(title)
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.show()

    def plot_test(self, Y, horizon, title, ylabel):
        fmt = mdates.DateFormatter('%d-%m-%Y')
        #loc = mdates.WeekdayLocator(byweekday=mdates.Monday)
        months = self._dates[self._N:self._N+horizon]

        target = self._data[self._N:self._N+horizon] 
        pred = Y.flatten()

        plt.figure(2).clear()
        plt.plot_date(x=months, y=target, fmt="-", color='blue')
        plt.plot_date(x=months, y=pred, fmt="-", color='red')
        plt.title(title)
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.show()
        

def main():
    # load data and stuff	
    # two-dimensional array?; date, price for a region and commodity
    # convert date to floats
    #data = np.loadtxt('oilprices.txt', delimiter=',', skiprows=1, unpack=True, converters={0 :mdates.strpdate2num('%Y-%m-%d')})

    data = np.genfromtxt('good_series_wholesale_daily.txt', usecols = (0, 1), delimiter=',', skiprows=1, unpack=True, converters={0:mdates.strpdate2num('%Y-%m-%d')})

    # Split dataset into training and testset
    print len(data[0])
    split_ind = len(data[0])-35

    # Reservoir size
    Nx = 1000
    initN = 740# 24 months initialization

    Ny = 1
    # Num. Regions and Products : R,P
    esn = ESN(data, split_ind, initN)
    esn.init_reservoir(Nx) 
    esn.custom_training()
    esn.plot_training('Training outputs', 'Y')
    Y = esn.generative_run(35)
    esn.plot_test(Y, 35, 'Test run', 'Price')

    #esn.custom_training("o", teacher_forcing = True, feedback = True, xTransOrder = False, leaky = True)

    """
    TODO: 
    * be able to switch from applying an additional nonlinear function to output
        => Wout: dim(order*N+2) CHECK
    * include possibility to save parameters after training
    * be able to switch between batch and online algorithm
        implement online RLS algorithm
    * integrate me bootstrap
    """


if __name__ == "__main__":
	main()

    
