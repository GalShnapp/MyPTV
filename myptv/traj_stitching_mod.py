# -*- coding: utf-8 -*-
"""
Created on Wed March 23 2022

@author: ron

An implementation for the trajectory segments stitching algorithm. We are 
looking to connect together trajectories that, for some reason, were broken 
during the tracking process, and to connect them together.

The algorithm is defined by Xu (2008): Haitao Xu, Tracking Lagrangian 
trajectories in position–velocity space, Meas. Sci. Technol. 19 (2008)
075105 (10pp) 
"""

from numpy import array, gradient, dot, savetxt
from numpy import append as NPappend
from myptv.utils import fit_polynomial
from myptv.traj_smoothing_mod import smooth_traj_poly


class traj_stitching(object):    
    '''
    Finds a list of trajectory pairs to connect to each
    other based on the algorithm of Xu(2008). For now we are not
    using trajectory acceleration information for the stitching.
    In addition, we also interpolate the "missing" samples at the connected
    interval by using a cubic polynomial that is fitted with the last and 
    first two data points of the connected trajectories.
    '''
    
    def __init__(self, traj_list, Ts, dm):
        '''
        inputs -
        traj_list - list, holding the trajectories. The algorihm relies
                    on the trajectories' velocity, so we input here
                    the results of smoothed trajectories. Use the same
                    format as the one saved in 
                    traj_smooth_mod.smooth_trajectories.save_results().
        Ts - float, the maximum allowable time separation allowed 
             for stitching
        dm - maximum distance (in r,v*dt space) for connection
        '''
        self.traj_list = traj_list
        self.Ts = Ts
        self.dm = dm

        # ===============================================================
        # for now we will not be using acceleratino data in the stitching
        # but the framework is prepared through the parameter wa. For now
        # it is zero, so acceleration is not used.
        self.wa = 0.0
        # ===============================================================


    def get_traj(self, i):
        '''
        given a trajectory number, i, this will return the trajectory data, 
        with samples sorted according to time.
        
        input -
        i - int, trajectory number
        '''
        key = lambda s: s[-1]
        tr = array(sorted(self.traj_list[self.traj_list[:,0] == i], key=key))
        return tr


    def calc_d(self, tr_i, tr_j):
        '''
        Taking 2 trajectories with trajectory numbers i and j. Trajectory i
        ends at time t_ie and trajectory j starts at time t_js; it is 
        necessary that t_ie < t_js.
        
        We project the position and velocity of particle i onto time t_js 
        assuming constant velocity: 
            x_i(t_js) = x_i(t_ie) + u_i(t_ie) * (t_js - t_ie)
            u_i(t_js) = u_i(t_ie)  (+ possible future acceleration term)
            
        Then, we calculae the distance between particle j and the projection
        of particle i at the start time of particle j
            dij = [ (x_i(t_js) - x_j(t_js))^2 + (u_i(t_js) - u_j(t_js))^2 ]^0.5
        
        * if a trajectory has more than one sample, we estimate its velocity
          based on simple forward differences. 
          
        ** For now, we do not attempt to connect single samples. This is 
           something that could be added in the future.
        
        
        return - if dij<=dm and t_js - t_ie < self.Ts: returns dij. 
                 Else, returns -1.
        '''
        # note the end and starting times
        t_ie = tr_i[-1,-1]
        t_js = tr_j[0,-1]
        
        # note their time separation:
        dt = t_js - t_ie
        if dt > self.Ts or dt<0:
            return -1
        
        # taking the position velocity and acceleration of trajectory i
        x_ie = tr_i[-1,1:4]
        v_ie = tr_i[-1,4:7]
        a_ie = tr_i[-1,7:10]
        
        # projecting particle i to time t_js
        x_i_js = x_ie + dt * v_ie
        v_i_js = v_ie + self.wa * dt * a_ie
        
        # calculating the distance between trajectories at t_js
        dx = sum((x_i_js - tr_j[0,1:4])**2)**0.5
        dv = sum((v_i_js - tr_j[0,4:7])**2)**0.5
        
        # calculate d_ij; if it's small enough return it, else return -1.
        dij = (dx**2 + dv**2)**0.5
        
        if dij<=self.dm: return dij
        else: return -1

    
    
    def calc_dij(self):
        '''
        Calculates dij for all possible trajectories and lists them.
        '''
        traj_ids = list(set(self.traj_list[:,0]))
        if -1 in traj_ids:
            traj_ids.remove(-1)
        
        traj_dic = {}
        for id_ in traj_ids:
            tr = self.get_traj(id_)
            v = tr[:,4:7]
            if (v==0).all():
                x = tr[:,1:4]
                v = gradient(x, axis=0)
                a = gradient(v, axis=0)
                tr[:,4:7] = v
                tr[:,7:10] = a
                
            traj_dic[id_] = tr 
        
        self.dij_list = []
        for id_i in traj_ids:
            for id_j in traj_ids:
                if id_i == id_j: continue
                dij = self.calc_d(traj_dic[id_i], traj_dic[id_j])
                if dij != -1:
                    dt = traj_dic[id_j][0,-1] - traj_dic[id_i][-1,-1]
                    self.dij_list.append((id_i, id_j, dt, dij))
    
    
    def find_best_stitch_candidates(self):
        '''
        After generating the dij list, if there are more than one possible
        connections to be made for any single trajectory, this function 
        discards the connections with the higher dij values.
        '''
        sort_d = lambda s: s[-1]
        dij_sorted = sorted(self.dij_list, key = sort_d)
        
        new_dij_list = []
        i_added = []
        j_added = []
        for dij in dij_sorted:
            i, j = dij[0], dij[1]
            
            if i in i_added or j in j_added:
                continue
            
            else:
                new_dij_list.append(dij)
                i_added.append(i)
                j_added.append(j)
                
        self.dij_list = new_dij_list
                
        
    def connect_traj(self):
        '''
        After finding the best candidates for stitching, this connects the
        trajectories. The connection is made by changing the trajectory number
        of the earlier trajectory (i) to that of the later trajectory (j).
        
        We also interpolate the "missing" samples at the connected interval
        by using a cubic polynomial that is fitted with the last and first 
        two data points of the connected trajectories.
        '''
        connected_traj_i = []
        connected_traj_j = []
        for i,j,dt,dij in self.dij_list:
            
            tr_i = self.get_traj(i)
            tr_j = self.get_traj(j)
            
            #if j was previously connected:
            while len(tr_j)==0:
                j = connected_traj_j[connected_traj_i.index(j)]
                tr_j = self.get_traj(j)
            
            # find the times that need to be filled in
            t_ie = tr_i[-1,-1]
            
            # get the trajectory positions needed for the polynomial fitting
            x_i = tr_i[-2:,1:4]   # <-- last two data points of i
            x_j = tr_j[:2, 1:4]   # <-- first two data points of j
            tm_fitting = [-1.0, 0.0, dt, dt+1.0]  # <-- time for fitting
            
            # the time needed to interpolate
            tm_interp = [float(i) for i in range(1,int(dt))]
            
            # in each direction fit a polynomial and fill missing samples
            interp_samples_j = [[j,0,0,0,0,0,0,0,0,0,tm_+t_ie] 
                              for tm_ in tm_interp]
            for k in range(3):
                x_ = list(x_i[:,k]) + list(x_j[:,k])
                poly_coefs = fit_polynomial(tm_fitting, x_, 3)
                for e, tm_ in enumerate(tm_interp):
                    # interpolate position
                    tm_vect = [tm_**3, tm_**2, tm_, 1.0]
                    x_interp = dot(poly_coefs, tm_vect)
                    interp_samples_j[e][1+k] = x_interp
                                       
            # add the interpolated samples to the traj_list
            self.traj_list = NPappend(self.traj_list, interp_samples_j, axis=0)
            
            # change the traj_number of traj i to j
            for k in range(len(self.traj_list)):
                if self.traj_list[k][0] == i:
                    self.traj_list[k][0] = j
            
            connected_traj_i.append(i)
            connected_traj_j.append(j)

            
        # finish by calculating the velocity and acceleration of the 
        # the stitched trajectory by using the smoothing function
        self.new_traj_list = []
        for id_ in list(set(self.traj_list[:,0])):
            
            # (we add the single samples at the end)
            if id_==-1:
                continue
            
            traj = self.get_traj(id_)
            if id_ in connected_traj_j:
                pos = traj[:,1:4]
                new_p, new_v, new_acc = smooth_traj_poly(pos.T, 5, 3)
                for i in range(len(pos)):
                    smp = [id_, 
                           pos[i][0], pos[i][1], pos[i][2],
                           new_v[0][i], new_v[1][i], new_v[2][i],
                           new_acc[0][i], new_acc[1][i], new_acc[2][i],
                           traj[i,-1]
                           ]
                    self.new_traj_list.append(array(smp))
                
            else:
                for smp in traj:
                    self.new_traj_list.append(smp)
        
        single_samples = self.get_traj(-1)
        for smp in single_samples:
            self.new_traj_list.append(smp)
            
        self.new_traj_list = array(self.new_traj_list)
        
        
        
    def stitch_trajectories(self):
        '''
        This performs all the steps of the trajectory stitching process.
        '''
        traj_ids = list(set(self.traj_list[:,0]))
        ntr = len(traj_ids)
        print('starting at %d trajectories'%(ntr))
        whr = self.traj_list[:,0] != -1
        nsmp = len(self.traj_list[whr])*1.0
        print('with %.1f samples per trajectory on average'%(nsmp/ntr),'\n')
        
        print('searching for candidates to connect')
        self.calc_dij()
        self.find_best_stitch_candidates()
        
        N = len(self.dij_list)
        print('found %d connections to be made'%N)
        print('connecting')
        ntraj0 = len(self.traj_list)
        self.connect_traj()
        print('finished connecting trajectories', '\n')
        
        print('interpolated %d new samples'%(len(self.traj_list) - ntraj0))
        traj_ids = list(set(self.traj_list[:,0]))
        ntr = len(traj_ids)
        print('finished with %d trajectories'%(ntr))
        whr = self.traj_list[:,0] != -1
        nsmp = len(self.traj_list[whr])*1.0
        print('at %.1f samples per trajectory on average'%(nsmp/ntr),'\n')    
            
    
    def save_results(self, fname):
        '''
        saves the results on the hard drive as a text file with a given file
        name.
        '''
        fmt = ['%d', '%.3f', '%.3f', '%.3f', '%.3f', '%.3f', '%.3f', '%.3f', 
               '%.3f', '%.3f', '%.3f']
        savetxt(fname, self.new_traj_list, fmt=fmt, delimiter='\t')
            
            