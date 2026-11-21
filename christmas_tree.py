#!/usr/bin/env python3
"""霜夜星愿 · 单文件三维粒子圣诞树

安装：python -m pip install "pygame>=2.5,<3" "numpy>=1.24"
启动：python christmas_tree.py
默认画布 1080×1920。F11 全屏，空格重播，Esc 退出。
画布在较小的桌面上等比预览。所有图案、文字纹理和光效均在启动或播放时生成。
"""
import argparse
import ctypes as ct
import ctypes.util
import math
import os
import sys
import weakref
from pathlib import Path
from time import perf_counter, sleep

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")

import numpy as np
import pygame
from pygame._sdl2 import Renderer, Texture, Window, WINDOWPOS_CENTERED


class Fir:
    """A whorled fir with individual side shoots, needles and hanging crystal beads."""

    star_y = 2.78
    camera_distance = 18.0
    view_sin = 0.118
    view_cos = (1 - view_sin**2) ** 0.5

    def __init__(self, seed=2412):
        rng = np.random.default_rng(seed)
        tau = 2 * np.pi
        self._blocks = []
        self._count = 0

        def add(xyz, kind, radius, light, axis=None):
            n = len(xyz)
            start = self._count
            self._count += n
            if axis is None:
                axis = np.broadcast_to((1.,0.,0.), (n,3))
            self._blocks.append(np.column_stack((
                xyz, np.broadcast_to(kind, (n,)), np.broadcast_to(radius, (n,)),
                np.broadcast_to(light, (n,)), rng.random(n),axis,
            )).astype(np.float32))
            return slice(start, self._count)

        def polar(r, a, y):
            return np.column_stack(np.broadcast_arrays(r * np.cos(a), y, r * np.sin(a)))

        # Branch whorls are slightly irregular in height, angular spacing, length and sweep.
        tier = np.linspace(0, 0.982, 14)
        counts = np.rint(4 + 6 * (1 - tier) ** .7).astype(int)
        u = np.repeat(tier, counts)
        angle = np.concatenate([
            tau * np.arange(n) / n + j * 2.39996 for j, n in enumerate(counts)
        ]) + rng.normal(0, .058, len(u))
        root_y = -1.44 + 3.92 * u + rng.normal(0, .023, len(u)) * (1 - u)
        length = (.06 + 1.85 * (1 - u) ** .82) * rng.uniform(.89, 1.10, len(u))
        sweep = rng.uniform(-.30, .30, len(u))
        droop = rng.uniform(.31, .40, len(u))
        direction = polar(1., angle, 0.)
        lateral = polar(1., angle + np.pi / 2, 0.)

        def spine(b, s):
            r = length[b] * (.018 + .982 * s)
            a = angle[b] + sweep[b] * s**1.36
            y = root_y[b] - length[b] * (droop[b] * np.sin(2.15*s) + .11*s - .12*s**5)
            return polar(r, a, y)

        # The rachis of each fern-like bough and its side shoots have independent directions.
        stem_counts = np.maximum(8, np.rint(45 * length).astype(int))
        branch = np.repeat(np.arange(len(u)), stem_counts)
        s = np.concatenate([np.linspace(.01, 1., n) for n in stem_counts])
        stem = spine(branch, s)
        stem_axis = spine(branch,np.minimum(1,s+.012))-spine(branch,np.maximum(0,s-.012))
        add(stem,0,rng.uniform(.006,.011,len(s)),rng.uniform(.49,.83,len(s)),stem_axis)

        shoot_counts = np.maximum(3, np.rint(3 + 6.3*length).astype(int))
        b = np.repeat(np.arange(len(u)), shoot_counts*2)
        s = np.concatenate([np.repeat(np.linspace(.08,.968,n),2) for n in shoot_counts])
        side = np.tile([-1.,1.],len(s)//2)
        s = np.clip(s + rng.normal(0,.006,len(s)),.04,.989)
        origin = spine(b,s)
        fork = length[b]*(.079+.39*(1-s)**.73)*rng.uniform(.86,1.11,len(s))
        # Each pair opens in a shallow V. Trace the curved twigs; splay regular, opposing
        # needles from real nodes on them rather than drawing independent points in a cone.
        along = (.57+.16*s)[:,None]*direction[b]+(.91*side)[:,None]*lateral[b]
        across = (-.91*side)[:,None]*direction[b]+(.57+.16*s)[:,None]*lateral[b]
        tilt = rng.uniform(.22,.47,len(s))
        def twig(index,q):
            p = origin[index]+(q*fork[index])[:,None]*along[index]
            p[:,1] += fork[index]*(tilt[index]*q + .29*q*q)
            return p

        ribs = np.maximum(3,np.rint(2+10*fork).astype(int))
        shoot = np.repeat(np.arange(len(s)),ribs)
        q = np.concatenate([np.linspace(.03,1.,n) for n in ribs])
        rib_axis = along[shoot].copy()
        rib_axis[:,1] = tilt[shoot]+.58*q
        add(twig(shoot,q),0,.0068+.0023*q,.45+.39*q,rib_axis)

        nodes = np.maximum(3,np.rint(2.7+9.8*fork).astype(int))
        i = np.repeat(np.arange(len(s)),2*nodes)
        q = np.concatenate([np.repeat((np.arange(n)+.3)/n,2) for n in nodes])
        # Opposite needles on each node share a base. The projected axes in project() keep
        # their feather pattern recognisable while the tree turns through a full circle.
        pair = np.tile([-1.,1.],len(i)//2)
        lean = .43+.28*q
        frost_axis = lean[:,None]*along[i]+(.81*pair)[:,None]*across[i]
        frost_axis[:,1] = .25+.39*q + rng.uniform(-.11,.13,len(i))
        needle_length = .024+fork[i]*(.27*(1-q)**.6+.065)
        base = twig(i,q) + (needle_length*.58)[:,None]*frost_axis
        light_facet = rng.uniform(.70,1.14,len(u))[b[i]]
        lux = (.41+.44*q+.11*s[i])*light_facet*rng.uniform(.84,1.13,len(i))
        silver = (q + .24*s[i] + rng.uniform(-.14,.12,len(i))) > .82
        radius = np.clip(.0062+.069*needle_length, .0064, .017)*rng.uniform(.87,1.08,len(i))
        add(base,np.where(silver,2,1),radius,lux,frost_axis)
        # Small grains of rime sit on the very tips; their radiance interrupts the uniform rows.
        selection = np.flatnonzero((q>.49)&(rng.random(len(q))<.28))
        grains = base[selection]+(.43*needle_length[selection])[:,None]*frost_axis[selection]
        add(grains,2,rng.uniform(.004,.008,len(grains)),rng.uniform(.40,1.04,len(grains)),
            frost_axis[selection])
        n = 410
        v = rng.random(n)
        a = rng.integers(0,13,n)*tau/13+.16*v+rng.normal(0,.034,n)
        add(polar(.036+.073*(1-v)**1.8,a,-2.33+4.85*v),0,
            rng.uniform(.005,.0078,n),rng.uniform(.28,.64,n),
            np.broadcast_to((0.,1.,0.),(n,3)))
        # An upright terminal shoot joins the final whorl to the five-pointed crown.
        v = np.linspace(0,1,101)
        a = np.arange(len(v))*2.39996
        spear = polar(.058*(1-v)**.7,a,2.32+.212*v)
        spear_axis = polar(.23,a,1.)
        add(spear,2,.0078+.005*(1-v),.56+.28*v,spear_axis)
        outer = np.flatnonzero(q>.57)
        selected = rng.choice(outer,360,replace=False)
        add(base[selected],3,rng.uniform(.009,.019,len(selected)),rng.uniform(.71,1.15,len(selected)))
        needle_end = self._count

        # Two hairline silver filaments braid around a softly sagging rope of ice-blue lamps.
        def cord(h, strand):
            a = tau * 4.12*h - .84
            turn = tau * (31*h + strand/2)
            taper = (1-h)**.72
            r = .055 + 2.01*(1-h)**.85 + .025*taper*np.sin(turn)
            y = -2.24 + 4.76*h + taper*(.040*np.cos(turn) - .065*np.sin(2*a+.59))
            return polar(r, a + .011*np.cos(turn), y)

        for j, n in enumerate((1800,1550)):
            h = np.linspace(0,1,n)
            add(cord(h,j), 4, .0062 + .0023*(1-h), rng.uniform(.54,.84,n))
        h = np.linspace(.001,.993,442)
        add(cord(h,.5),5, rng.uniform(.011,.022,len(h)), rng.uniform(.83,1.27,len(h)))
        self._ribbon = slice(needle_end,self._count)

        # Sectioned orbital tracks, a toothed edge and isolated floor glitter.
        ring_start = self._count
        angular_speeds = []
        for j,(r,y,n,speed) in enumerate((
            (2.34,-2.36,990,.048), (2.25,-2.35,710,-.046),
            (2.05,-2.31,870,.077), (1.69,-2.29,620,-.083),
        )):
            a = np.linspace(0,tau,n,endpoint=False)
            if j in (1,3):
                a = a[np.cos((3+j)*a+.9*j)>-.69]
            engraving = .64+.34*np.cos((7+j)*a)**2
            add(polar(r,a,y),6, .0058 if j in (1,3) else .0084, engraving)
            angular_speeds.append(np.full(len(a),speed, np.float32))
        a = np.repeat(tau*np.arange(84)/84,4)
        r = 2.34 - np.tile(np.linspace(0.,1.,4),84)*np.repeat(np.where(np.arange(84)%7==0,.081,.033),4)
        add(polar(r,a,-2.36),6,.0073,.69)
        angular_speeds.append(np.full(len(a),.048, np.float32))
        self._rings = slice(ring_start,self._count)
        self._ring_speed = np.concatenate(angular_speeds)
        n = 685
        self._floor = add(polar(.35 + 2.20*rng.random(n)**.63, rng.random(n)*tau,
                                -2.35+rng.normal(.014,.043,n)),7,
                          rng.uniform(.0045,.011,n), rng.uniform(.17,.51,n))

        # Baubles really hang from the tips of individual side branches.
        eligible = np.flatnonzero(u < .96)
        b = rng.choice(eligible,94,replace=False,p=length[eligible]**.43 / sum(length[eligible]**.43))
        size = rng.uniform(.052,.111,len(b))*(.64+.36*(1-u[b]))
        anchor = spine(b,rng.uniform(.77,.99,len(b)))
        anchor[:,1] -= size*1.34
        self._balls = add(anchor,rng.choice((8,9,10),len(b),p=(.36,.28,.36)),size,
                          rng.uniform(.78,1.10,len(b)))

        # The optical shockwave is a real tilted ring of loose particles in world space.
        n = 520
        a = np.linspace(0,tau,n,endpoint=False)+rng.normal(0,.004,n)
        radial = 1. - .15*rng.random(n)**3
        self._wave_vector = np.column_stack((np.cos(a)*radial,
                     np.sin(a)*radial*.80, np.sin(a)*radial*.60)).astype(np.float32)
        self._wave = add(np.zeros((n,3)),11,rng.uniform(.007,.018,n),rng.uniform(.38,1.1,n))
        points = np.concatenate(self._blocks)
        del self._blocks
        self._x,self._y,self._z = (np.ascontiguousarray(v) for v in points[:,:3].T)
        self._kind = points[:,3].astype(np.uint8)
        self._radius,self._light,self._seed = (np.ascontiguousarray(v) for v in points[:,4:7].T)
        self._ax,self._ay,self._az = (np.ascontiguousarray(v) for v in points[:needle_end,7:].T)
        self._radial_inv = 1./np.maximum(.075,np.hypot(self._x,self._z))
        self._height = np.clip((self._y+2.26)/4.77,0,1)
        self._canopy = slice(0,needle_end)
        self._arrival_start = (.11 + 2.17*self._height[:needle_end] + .77*self._seed[:needle_end])
        self._arrival_span = (2.88 + .93*self._height[:needle_end]+.28*self._seed[:needle_end])
        # The incoming stars share moving streamlines; independent offsets loosen the trails.
        clouds = rng.integers(0,21,needle_end)
        along = rng.random(needle_end)
        lane_phase = clouds*2.39996
        self._from_angle = np.asarray(lane_phase + .95*along + rng.normal(0,.105,needle_end),'f4')
        self._from_radius = np.asarray(4. + 4.1*along + 1.05*np.sin(lane_phase),'f4')
        self._from_y = np.asarray(5.8*np.sin(lane_phase*1.43) + 1.5*(along-.5)
                                  + rng.normal(0,.46,needle_end),'f4')
        self._phase = (self._seed*231.).astype('f4')
        self._tempo = (.94+1.55*self._seed).astype('f4')

    @staticmethod
    def _ease(x):
        x = np.clip(x,0,1)
        return x*x*(3-2*x)

    @staticmethod
    def _scale(width,height):
        return min(width*.180, height*.100)

    def star_screen(self,t,width,height):
        depth = self.camera_distance-self.view_sin*self.star_y
        scale = self._scale(width,height)*self.camera_distance/depth
        return (width*.5,height*.545-self.star_y*self.view_cos*scale,.297*scale,depth)

    def project(self,t,width,height):
        # Rotations act on fixed world coordinates and never accumulate integration error.
        canopy, rope, rings, balls, wave = self._canopy,self._ribbon,self._rings,self._balls,self._wave
        yaw = t*.103-.47
        co,si = np.cos(yaw).astype('f4'),np.sin(yaw).astype('f4')
        x = self._x*co + self._z*si
        z = self._z*co - self._x*si
        y = self._y.copy()
        light = self._light*(.81 + .19*np.sin(self._phase + self._tempo*t))
        light *= .96+.04*np.sin(1.23*t)
        if t < 7.5:
            g = self._ease((t-self._arrival_start)/self._arrival_span)
            k = 1.-g
            phase = self._from_angle + 1.75*k + .24*t
            sx = np.cos(phase)*self._from_radius
            sz = np.sin(phase)*self._from_radius
            sy = self._from_y + .68*np.sin(phase+.91*t)
            x[canopy] = g*x[canopy] + k*sx
            z[canopy] = g*z[canopy] + k*sz
            y[canopy] = g*y[canopy] + k*sy + .55*np.sin(np.pi*g)
            free = (.09+.51*self._seed[canopy]**6) * (.22+.78*self._ease(t/.85))
            light[canopy] *= g**2 +(1-g**2)*free

        front = np.clip(z*self._radial_inv,-1.,1.)
        side_light = np.clip(-x[canopy]*self._radial_inv[canopy],-1.,1.)
        light[canopy] *= .085 + .99*self._ease(.38+.68*front[canopy]) + .068*side_light
        # The interior of each bough stays darker, opening distinct gaps between the lit skirts.
        light[canopy] *= .78 + .22*self._ease((self._radial_inv[canopy]**-1)*1.8)
        # The return span of the cable dims where it passes through the back of the tree.
        flow = (.5+.5*np.cos(31.5*self._height[rope]-2.62*t))**6
        light[rope] *= (.67+.83*flow)*(.24+.82*self._ease(.52+.56*front[rope]))
        light[rope] *= self._ease((t-5.38-1.99*self._height[rope])/.75)
        light[balls] *= (.24+.83*self._ease(.53+.60*front[balls]))
        if t < 7.5:
            light[balls] *= self._ease((t-2.52-3.55*self._height[balls])/.91)

        phase = self._ring_speed*t
        cs,sn = np.cos(phase),np.sin(phase)
        x[rings] = self._x[rings]*cs+self._z[rings]*sn
        z[rings] = self._z[rings]*cs-self._x[rings]*sn
        light[rings] *= (.77+.18*z[rings]*self._radial_inv[rings]) * self._ease((t-1.46)/2.46)
        light[self._floor] *= self._ease((t-1.72)/3.2)
        if 8.44 < t < 10.86:
            p = (t-8.44)/2.42
            radius = .10+3.30*(1-(1-p)**1.8)
            spread = radius*(1.+.023*p*np.sin(self._phase[wave]))
            x[wave] = self._wave_vector[:,0]*spread
            y[wave] = self.star_y+self._wave_vector[:,1]*spread
            z[wave] = self._wave_vector[:,2]*spread
            light[wave] *= self._ease(p/.065)*(1-self._ease((p-.15)/.85))*(1.28-.48*p)
        else:
            light[wave] = 0.

        depth = self.camera_distance - self.view_sin*y - self.view_cos*z
        pixels = self._scale(width,height)*self.camera_distance/np.maximum(depth,1.)
        sx = width*.5 + x*pixels
        sy = height*.545 - (self.view_cos*y-self.view_sin*z)*pixels
        radius = self._radius*pixels
        if t < 7.5:
            radius[balls] *= self._ease((t-2.52-3.55*self._height[balls])/.91)
        visible = ((light>.009) & (depth>1.) & (sx>-radius*4) & (sx<width+radius*4)
                   & (sy>-radius*4) & (sy<height+radius*4))
        # Differentiate the perspective divide: a radial shoot viewed nearly end-on
        # foreshortens and rotates correctly even away from the principal camera axis.
        vx = co*self._ax+si*self._az
        vz = co*self._az-si*self._ax
        toward = (self.view_sin*self._ay+self.view_cos*vz)/depth[canopy]
        dx = vx+x[canopy]*toward
        dy = -(self.view_cos*self._ay-self.view_sin*vz
               + (self.view_cos*y[canopy]-self.view_sin*z[canopy])*toward)
        norm = np.maximum(1.e-7,np.hypot(dx,dy))
        axes = np.empty((len(x),2),'f4')
        axes[canopy,0],axes[canopy,1] = dx/norm,dy/norm
        axes[canopy.stop:] = (1.,0.)
        # Keeping an opaque depth coordinate lets the rasterizer composite back-to-front.
        xy = np.column_stack((sx[visible],sy[visible]))
        return xy,depth[visible],self._kind[visible],light[visible],radius[visible],axes[visible]


class WinterSky:
    """A folded aurora, cold stellar dust, and depth-layered falling snow."""

    def __init__(self, size, seed=1247):
        self.width, self.height = (max(1, int(v)) for v in size)
        rng = np.random.default_rng(seed)
        self.unit = max(.45, min(self.width / 670., self.height / 1130.))
        self._make_atmosphere(rng)
        self._make_starfield(rng)
        self._make_snow(rng)
        self._sky_tick = None
        self._sky_image = None
        self._background = None

    @staticmethod
    def _rise(a, b, t):
        u = min(1., max(0., (t - a) / (b - a)))
        return u * u * (3. - 2. * u)

    def _make_atmosphere(self, rng):
        # Two folded emission curtains. Narrow ridges along their lower edges
        # feather upward into vertical striations. The void between them frames the fir.
        w, h = self.width, self.height
        ratio = min(1., 310. / h, 255. / w)
        self._cloud_size = (max(16, round(w * ratio)), max(16, round(h * ratio)))
        sw, sh = self._cloud_size
        y, x = np.mgrid[:sh, :sw].astype(np.float32)
        x /= max(1, sw - 1)
        y /= max(1, sh - 1)

        def noise_at(nx, ny):
            grid = rng.random((ny + 1, nx + 1), dtype=np.float32)
            gx, gy = x * (nx - .001), y * (ny - .001)
            ix, iy = gx.astype(np.int32), gy.astype(np.int32)
            fx, fy = gx - ix, gy - iy
            fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
            upper = grid[iy, ix] * (1 - fx) + grid[iy, ix + 1] * fx
            lower = grid[iy + 1, ix] * (1 - fx) + grid[iy + 1, ix + 1] * fx
            return ((1 - fy) * upper + fy * lower).astype(np.float32)

        cloud = (.49 * noise_at(5, 7) + .29 * noise_at(12, 14)
                 + .16 * noise_at(29, 37) + .06 * noise_at(61, 73))
        texture = (cloud - .48) * 2.4
        left = np.exp(-((x - .08) / .29) ** 2)
        right = np.exp(-((x - .94) / .30) ** 2)
        edge = .13 + .72 * left + .92 * right
        void = np.exp(-((x - .50) / .27) ** 2 - ((y - .53) / .33) ** 2)
        haze = np.exp(-((x - .80) / .95) ** 2 - ((y - .30) / .52) ** 2)
        diagonal = np.exp(-((y - .04 - .56 * x - .11 * np.sin(5 * x)) / .105) ** 2)
        secondary = np.exp(-((y - .61 - .16 * np.cos(4.5 * x)) / .096) ** 2)
        mist = (1.8 + 15.0 * diagonal + 11.5 * secondary) * (.24 + 1.42 * cloud)
        mist *= 1. - .60 * void
        # Coherent keyframes blend without a seam over the full atmospheric cycle.
        self._cloud_frames = []
        for phase in np.linspace(0., 2. * np.pi, 24, endpoint=False):
            q = x + .32 * (y - .32) + .009 * np.sin(9 * y + phase)
            foot = (.30 + .095 * np.sin(5.7 * q + .16 * np.sin(phase))
                    + .050 * np.sin(14.3 * q + .60 + .30 * np.cos(phase))
                    + .017 * np.sin(27 * q + .4 * np.sin(phase)))
            above = foot - y
            warp = q + .016 * np.sin(17 * q + phase) + .011 * np.cos(39 * q - phase)
            bars = (.51 + .19 * np.sin(138 * warp) + .13 * np.sin(288 * warp + .55)
                    + .17 * np.sin(55 * warp - .6))
            tail = .079 + .033 * np.sin(15 * q + .6 * np.sin(phase)) + .030 * bars
            plumes = np.exp(-np.maximum(above, 0.) / tail - np.maximum(-above, 0.) / .016)
            hem = np.exp(-(above / .013) ** 2)
            curtain = edge * (plumes * (8. + 25. * bars) + hem * (5. + 9. * bars))
            q2 = x - .28 * (y - .31)
            foot2 = (.35 + .086 * np.sin(6.6 * q2 + 1.04 + .23 * np.cos(phase))
                     - .041 * np.cos(17.5 * q2 + .25 * np.sin(phase)))
            above2 = foot2 - y
            ribbon = np.exp(-np.maximum(above2, 0.) / .075 - np.maximum(-above2, 0.) / .011)
            threads = .5 + .5 * np.sin(96 * q2 + 1.7 * np.sin(19 * q2 + phase))
            curtain += (.30 * left + .76 * right) * ribbon * (8. + 14. * threads)
            curtain *= 1.34 * (1 + .28 * texture) * (1. - .48 * void)
            living_mist = mist * (.83 + .19 * np.sin(5 * x - 8 * y + phase + texture))
            r = 1.7 + 1.8 * haze + living_mist * .48 + curtain * .40
            g = 3.1 + 3.1 * haze + living_mist * .97 + curtain * .96
            b = 7.0 + 6.0 * haze + living_mist * 1.7 + curtain * 1.55
            frame = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
            self._cloud_frames.append(frame)

    @staticmethod
    def _glow_sprite(diameter, tint, shape, angle=0.):
        diameter = max(3, int(diameter) | 1)
        center = (diameter - 1) * .5
        y, x = np.mgrid[:diameter, :diameter].astype(np.float32)
        x, y = (x - center) / max(1., center), (y - center) / max(1., center)
        r = np.sqrt(x*x + y*y)
        if shape == 'star':
            arms = np.exp(-21. * np.minimum(np.abs(x), np.abs(y))) * np.maximum(0., 1.-r) ** 2.2
            energy = .69 * np.exp(-30. * r*r) + .42 * arms + .095 * np.exp(-5. * r*r)
        elif shape == 'crystal':
            polar = np.arctan2(y, x) - angle
            delta = np.abs((polar + np.pi / 6.) % (np.pi / 3.) - np.pi / 6.)
            across, along = r * np.sin(delta), r * np.cos(delta)
            width = max(.028, .65 / center)
            spine = np.exp(-(across / width) ** 2) * np.maximum(0., 1. - along ** 3)
            forks = np.zeros_like(r)
            for knot in (.32, .56):
                dist = np.abs(across - .88 * (along - knot))
                branch = np.exp(-(dist / width) ** 2) * (along > knot) * (along < knot + .21)
                forks = np.maximum(forks, branch)
            energy = .62 * np.maximum(spine, .85 * forks) + .28 * np.exp(-9. * r*r)
        elif shape == 'bokeh':
            energy = np.exp(-2.5 * r*r) * np.maximum(0., 1. - r*r) ** 1.4
        else:
            energy = .86 * np.exp(-13. * r*r) + .17 * np.exp(-3.5 * r*r)
        energy *= np.clip((1.-r)*5., 0., 1.)
        rgb = (energy[..., None] * np.asarray(tint)).clip(0., 255.).astype(np.uint8)
        return pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))

    def _make_starfield(self, rng):
        # Immutable emission layers are shared between software and accelerated targets.
        w, h = self.width, self.height
        scale = min(1., .82 / self.unit)
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        pixels = np.zeros((sh, sw, 3), dtype=np.uint8)
        number = max(380, min(1600, round(w*h / (self.unit*self.unit*820))))
        sx, sy = rng.random((2, number))
        # A loose band of finer stars follows the diagonal interstellar dust.
        band = number // 3
        sy[:band] = np.mod(.05 + .56 * sx[:band] + .105 * np.sin(5 * sx[:band])
                            + rng.normal(0., .060, band), 1.)
        value = 9. + 88. * rng.random(number) ** 2.5
        v = value[:, None] * np.array([.48, .72, 1.])
        index = (np.minimum(sh-1, (sy*sh).astype(int)), np.minimum(sw-1, (sx*sw).astype(int)))
        np.maximum.at(pixels, index, v.astype(np.uint8))
        self._dust_layers = [
            pygame.surfarray.make_surface(np.transpose((pixels * gain).astype(np.uint8), (1, 0, 2)))
            for gain in (.20, .49, .77, 1.)
        ]
        self._dust_full = {}
        count = max(18, min(46, round(number * .032)))
        self._stars = rng.random((count, 5))
        self._star_atlas = {}
        for s in range(3):
            diam = max(5., (7. + 5.5 * s) * self.unit)
            for brightness in range(7):
                value = 18. + 18.5 * brightness
                self._star_atlas[s, brightness] = self._glow_sprite(
                    diam, (.69*value, .84*value, value), 'star'
                )

    def _make_snow(self, rng):
        w, h = self.width, self.height
        count = max(90, min(205, round(w*h / (self.unit*self.unit*5100))))
        self._flakes = rng.random((count, 6))
        depth = self._flakes[:, 2] ** 1.32
        self._fall = .012 + .044 * depth
        self._wind = .0060 + .016 * depth
        # Small grains, distant and nearby defocus, and a few resolved ice crystals.
        types = np.where(depth < .46, 0, np.where(depth < .78, 1, 2))
        types[(depth > .70) & (self._flakes[:, 4] > .77)] = 3
        self._flake_types = types.astype(int)
        self._flake_atlas = {}
        for typ, diam, v, shape in ((0, 3.0, 49., 'soft'), (1, 6.0, 69., 'soft'),
                                    (2, 15., 25., 'bokeh'), (3, 15.5, 81., 'crystal')):
            for frame in range(6):
                angle = frame * np.pi / 18.
                for light in range(4):
                    level = (.26 + light*.25) * v
                    self._flake_atlas[typ, frame if typ == 3 else 0, light] = (
                        self._glow_sprite(diam * self.unit, (.69*level, .85*level, level),
                                          shape, angle)
                    )
                if typ != 3:
                    break

    def _sky_frame(self, t):
        tick = int(t * 12.)
        if tick != self._sky_tick:
            # A fresh, small surface makes changed pixels explicit to texture caches.
            self._sky_tick = tick
            pos = (tick / (12. * 52.)) * len(self._cloud_frames)
            ia = int(pos) % len(self._cloud_frames)
            ib = (ia + 1) % len(self._cloud_frames)
            k = pos % 1.
            appear = .08 + .92 * self._rise(.25, 5.5, tick / 12.)
            pixels = self._cloud_frames[ia] * np.float32((1.-k)*appear)
            pixels += self._cloud_frames[ib] * np.float32(k*appear)
            self._sky_image = pygame.surfarray.make_surface(
                np.transpose(pixels.astype(np.uint8), (1, 0, 2)))
            self._background = None
        return self._sky_image

    def draw_background(self, surface, t):
        w, h = self.width, self.height
        sky = self._sky_frame(t)
        dust_level = min(3, max(0, int(t * 1.85)))
        far = self._dust_layers[dust_level]
        if hasattr(surface, 'blit_scaled'):
            surface.blit_scaled(sky, (0, 0, w, h))
            surface.blit_scaled(far, (0, 0, w, h), additive=True)
        else:
            if self._background is None or self._last_dust != dust_level:
                self._background = pygame.transform.smoothscale(sky, (w, h))
                if dust_level not in self._dust_full:
                    self._dust_full[dust_level] = pygame.transform.smoothscale(far, (w, h))
                self._background.blit(self._dust_full[dust_level], (0, 0),
                                      special_flags=pygame.BLEND_RGB_ADD)
                self._last_dust = dust_level
            surface.blit(self._background, (0, 0))
        appear = self._rise(.1, 2.75, t)
        for x, y, z, phase, size in self._stars:
            flicker = .53 + .47 * np.sin(phase*24. + t*(.35 + z*.67))
            bright = min(6, int((1. + 5.9 * flicker) * appear))
            if bright == 0:
                continue
            stamp = self._star_atlas[min(2, int(size**1.7 * 3)), bright]
            d = stamp.get_width() // 2
            surface.blit(stamp, (round(x*w)-d, round(y*h)-d), special_flags=pygame.BLEND_RGB_ADD)

    def draw_snow(self, surface, t):
        appear = self._rise(.80, 5.80, t)
        if appear < .07:
            return
        f = self._flakes
        # Margin wrapping keeps entering and departing flakes off the visible edge.
        sx = (f[:, 0] + t*self._wind + (.008 + .012*f[:, 2])
              * np.sin(.36*t + 28.*f[:, 3] + 4.*f[:, 1])) % 1.04
        sy = (f[:, 1] + t*self._fall) % 1.04
        angles = ((t*(.31 + .39*f[:, 3]) + f[:, 0]*6.) % 6.).astype(int)
        bright = np.clip(((1.75 + 1.65*np.sin(t*.57 + f[:, 5]*13.))*appear).astype(int), 0, 3)
        positions = np.column_stack(((sx-.02)*self.width, (sy-.02)*self.height)).astype(int)
        for (x, y), typ, frame, b in zip(positions, self._flake_types, angles, bright):
            if b == 0 and appear < .60:
                continue
            stamp = self._flake_atlas[typ, frame if typ == 3 else 0, b]
            d = stamp.get_width() // 2
            surface.blit(stamp, (int(x)-d, int(y)-d), special_flags=pygame.BLEND_RGB_ADD)


# --- Silver lettering and the cut-crystal tree topper --------------------------------


def _ice_ease(start, end, time):
    u = max(0.0, min(1.0, (time - start) / (end - start)))
    return u * u * (3.0 - 2.0 * u)


def _ice_rgba(rgb, alpha):
    """Make a straight-alpha pygame texture without needing an active display surface."""
    h, w = alpha.shape
    sprite = pygame.Surface((w,h), pygame.SRCALPHA, 32)
    # The native channel order also enables the fast alpha blitter in software mode.
    rgb8 = np.rint(np.clip(rgb, 0, 255)).astype(np.uint8)
    pixels = pygame.surfarray.pixels3d(sprite)
    pixels[:] = np.broadcast_to(rgb8, (h,w,3)).swapaxes(0,1)
    del pixels
    coverage = pygame.surfarray.pixels_alpha(sprite)
    coverage[:] = np.rint(np.clip(alpha.T, 0., 1.)*255).astype(np.uint8)
    del coverage
    return sprite


def _ice_blur(alpha, radius):
    """Three box convolutions approximate a Gaussian. This runs once at typesetting."""
    r = max(1, int(round(radius)))
    kernel = 2 * r + 1
    value = alpha.astype(np.float32)
    for _ in range(3):
        for axis in (0, 1):
            value = np.swapaxes(value, axis, 0)
            sums = np.cumsum(np.pad(value, ((r + 1, r), (0, 0))), axis=0, dtype=np.float32)
            value = np.swapaxes((sums[kernel:] - sums[:-kernel]) / kernel, axis, 0)
    return np.clip(value, 0, 1)


def _ice_font(title, pixels):
    if title:
        files = (
            "/usr/share/fonts/opentype/urw-base35/Z003-MediumItalic.otf",
            "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
        )
        families = "z003,urwchanceryl,p052,liberationserif,dejavuserif"
    else:
        files = (
            "/usr/share/fonts/opentype/urw-base35/P052-Italic.otf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
        )
        families = "p052,liberationserif,dejavuserif"
    face = next((path for path in files if os.path.isfile(path)), None)
    if face is None:
        face = pygame.font.match_font(families, italic=True)
    font = pygame.font.Font(face, pixels)
    if face is None:
        font.set_italic(True)
    return font


def _ice_inscription(text, width, title):
    # Typeset large first, then rasterize at final size. Counters and hairlines stay open.
    font = _ice_font(title, 196 if title else 120)
    letters = font.render(text, True, (255, 255, 255))
    letters = letters.subsurface(letters.get_bounding_rect(min_alpha=1))
    height = max(1, round(width * letters.get_height() / letters.get_width()))
    letters = pygame.transform.smoothscale(letters, (width, height))
    margin = max(9, round(height * (0.34 if title else 0.39)))
    extra = round(height * 0.36) if title else 0
    plate = pygame.Surface((width + 2 * margin, height + 2 * margin + extra), pygame.SRCALPHA)
    plate.blit(letters, (margin, margin))
    if title:
        # Fine symmetric engraving below the calligraphy, with a tiny central crystal.
        cx, cy = plate.get_width()/2, margin + height + extra*0.76
        span = max(12, width*0.083)
        for sign in (-1, 1):
            points = [(cx+sign*span*(0.16+i/28*0.84),
                       cy - height*0.009*math.sin(i*math.pi/28)) for i in range(29)]
            pygame.draw.aalines(plate, (232, 241, 255, 163), False, points)
        d = max(1.6, height*.034)
        pygame.draw.polygon(plate, (232, 243, 255, 205),
                            ((cx, cy-d), (cx+d*.56, cy), (cx, cy+d), (cx-d*.56, cy)))
    a = pygame.surfarray.array_alpha(plate).T.astype(np.float32) / 255
    near = _ice_blur(a, height * (0.032 if title else 0.039))
    far = _ice_blur(a, height * (0.10 if title else 0.095))
    line = max(1, round(height*0.014))
    # A real, narrow pale-blue keyline surrounds the stems independently of the blur.
    outline = np.maximum.reduce((np.roll(a, line, 0), np.roll(a, -line, 0),
                                 np.roll(a, line, 1), np.roll(a, -line, 1), a))
    edge = (1.0 - a) * outline * (0.83 if title else 0.47)
    halo = (1.0-a-edge) * np.minimum(0.92, near*0.99 + far*0.96)
    alpha = a + edge + halo
    y, x = np.ogrid[:a.shape[0], :a.shape[1]]
    gleam = 0.49 + 0.26*np.cos((y-margin)/max(1,height)*7.2-0.35)+0.16*np.cos(x/width*9.0)
    gleam = np.clip(gleam, 0, 1)[..., None]
    dark = np.array([172, 196, 224] if title else [157, 183, 216], dtype=np.float32)
    face = dark + gleam*(np.array([255, 255, 255], dtype=np.float32) - dark)
    premultiplied = (a[..., None]*face + edge[..., None]*[117, 181, 252] +
                     halo[..., None]*[51, 122, 238])
    return _ice_rgba(premultiplied/np.maximum(alpha[..., None], 1.0e-6), alpha), margin, height


class IceLettering:
    """Resolve system faces once; each animated caption needs one cached texture blit."""
    def __init__(self, size):
        if not pygame.font.get_init():
            pygame.font.init()
        w, h = size
        # Height limits also place both lines gracefully on landscape preview surfaces.
        title_w = max(20, round(min(w*0.78, h*.50)))
        wish_w = max(20, round(min(w*.58, h*.37)))
        self.title, margin, cap_h = _ice_inscription("Merry Christmas", title_w, True)
        self.title_at = ((w - self.title.get_width())//2, round(h*.119 - cap_h*.5) - margin)
        name = "wyj"
        font_path = pygame.font.match_font("notoserifcjksc,notosanscjksc,wqyzenhei")
        font = pygame.font.Font(font_path, max(16, round(h * 0.023)))
        self.name = font.render(name, True, (255, 182, 213))
        self.name_at = self.name.get_rect(center=(w // 2, round(h * 0.20))).topleft
        self.wish, margin, cap_h = _ice_inscription("May all your wishes come true.", wish_w, False)
        self.wish_at = ((w - self.wish.get_width())//2, round(h*.918 - cap_h*.5) - margin)

    def draw(self, surface, t):
        for sprite, position, opacity in (
                (self.title, self.title_at, _ice_ease(8.75, 11.3, t)),
                (self.name, self.name_at, _ice_ease(9.2, 11.6, t)),
                (self.wish, self.wish_at, _ice_ease(10.1, 12.65, t))):
            if opacity > 0:
                sprite.set_alpha(round(255*opacity))
                surface.blit(sprite, position)


class IceTopper:
    """Five extruded crystal points, blue atmospheric bloom and diffraction highlights."""
    def __init__(self):
        self.radius = 0
        self.faces = {}

    @staticmethod
    def _auras(radius):
        extent = math.ceil(4.50*radius)
        y, x = np.ogrid[-extent:extent+1, -extent:extent+1]
        x, y = x/radius, y/radius
        r = np.hypot(x, y)
        fade = np.minimum(1, np.maximum(0, (4.48-r)*1.38))
        haze = (0.43*np.exp(-1.62*r*r) + 0.22*np.exp(-0.92*r))*fade
        alpha = np.clip(haze, 0, .89)
        # A continuous radial shift from pale ice at the heart to deep celestial blue.
        intensity = np.exp(-r*0.82)
        color = np.stack([44+119*intensity, 102+109*intensity, 219+36*intensity], axis=-1)
        halo = _ice_rgba(color, alpha)
        ray = np.zeros_like(r)
        for angle, width, length, strength in (
                (.03, .022, 1.7, .63), (math.pi*.5+.03, .023, 1.66, .51),
                (math.pi*.25+.13, .031, .92, .29), (math.pi*.75+.13, .031, .92, .26)):
            across = abs(-x*math.sin(angle)+y*math.cos(angle))
            along = abs(x*math.cos(angle)+y*math.sin(angle))
            ray += strength*np.exp(-across/(width+.018*along))*np.exp(-along/length)
        ray = np.clip((ray+.22*np.exp(-r*r/2.9))*fade, 0, 1)
        return halo, _ice_rgba(np.array([161, 216, 255]), ray)

    @staticmethod
    def _cut(radius, phase):
        # Front and back differ in depth. Perspective yaw and normals are evaluated
        # for the individual triangular planes, including the ten fine edge bevels.
        zoom = 3
        extent = math.ceil(radius*1.16)
        side = extent*2+1
        canvas = pygame.Surface((side*zoom, side*zoom), pygame.SRCALPHA)
        angles = np.pi/2 + np.arange(10)*np.pi/5
        dist = np.tile((1.0, .415), 5)
        edge = np.column_stack((dist*np.cos(angles), dist*np.sin(angles), np.zeros(10)))
        inner = edge.copy()
        inner[:, :2] *= .905
        inner[:, 2] = .044
        center = np.array([0, .014, .343])
        theta = .1+.30*math.sin(phase)
        c, s = math.cos(theta), math.sin(theta)
        rot = np.array(((c,0,s),(0,1,0),(-s,0,c)))
        light = np.array((-.53+.19*math.cos(phase), .68, .61))
        light /= np.linalg.norm(light)

        def project(v):
            p = rot @ v
            f = radius*zoom*(4.7/(4.7-p[2]))
            return (extent*zoom + p[0]*f, extent*zoom - p[1]*f)

        def ice(level):
            v = np.clip(level, 0, 1)
            dark = np.array([90, 137, 193])
            return tuple(np.rint(dark + (np.array([252,254,255])-dark)*v).astype(int))

        for i in range(10):
            j = (i+1) % 10
            n = rot @ np.cross(inner[i]-center, inner[j]-center)
            n /= np.linalg.norm(n)
            level = max(0, float(n @ light))
            pygame.draw.polygon(canvas, ice(.12 + .88*level**1.9),
                                (project(center), project(inner[i]), project(inner[j])))
            bevel = .90 if (i % 3 == 0) else .37+.56*level
            pygame.draw.polygon(canvas, ice(bevel),
                                (project(edge[i]), project(edge[j]), project(inner[j]), project(inner[i])))
        for i in (0, 2, 6):
            pygame.draw.aaline(canvas, (205, 232, 255), project(center), project(inner[i]))
        return pygame.transform.smoothscale(canvas, (side, side))

    @staticmethod
    def _center_blit(target, sprite, x, y, opacity):
        sprite.set_alpha(max(0, min(255, round(opacity*255))))
        target.blit(sprite, (round(x - sprite.get_width()/2), round(y - sprite.get_height()/2)))

    def prepare(self, radius):
        # Called during startup to warm the only relatively large generated halo.
        key = max(2, round(radius/2)*2)
        if key != self.radius:
            self.radius = key
            self.halo, self.rays = self._auras(key)
            self.faces.clear()
        return key

    def draw(self, surface, t, x, y, radius):
        strength = _ice_ease(7.94, 8.70, t)
        if strength <= 0 or radius < 1:
            return
        # Quantize the projected radius to avoid rebuilding glows from subpixel drift.
        key = self.prepare(radius)
        phase_index = math.floor((t*.47) % math.tau / math.tau * 32)
        if phase_index not in self.faces:
            self.faces[phase_index] = self._cut(key, phase_index*math.tau/32)
        flash = math.exp(-((t-8.53)/.43)**2)
        pulse = .5+.5*math.sin(t*1.51)
        self._center_blit(surface, self.halo, x, y, strength*(.70+.10*pulse+.20*flash))
        self._center_blit(surface, self.rays, x, y, strength*(.31+.08*pulse+.61*flash))
        self._center_blit(surface, self.faces[phase_index], x, y, strength)


# Pygame owns the window, textures and SDL renderer. Its Python interface doesn't
# expose SDL_RenderGeometryRaw, so this small binding submits the NumPy buffers
# to the very same SDL instance, in one depth-ordered batch.
class SDLGeometry:
    def __init__(self, window):
        libs = Path(pygame.__file__).resolve().parent.parent / 'pygame.libs'
        candidates = list(libs.glob('libSDL2-2*.so*'))
        candidates.append(ct.util.find_library('SDL2-2.0') or 'libSDL2-2.0.so.0')
        ptr = ct.c_void_p
        integer = ct.c_int
        signatures = {
            'SDL_GetWindowFromID': (ptr, ct.c_uint32),
            'SDL_GetRenderer': (ptr, ptr),
            'SDL_GetError': (ct.c_char_p,),
            'SDL_CreateTexture': (ptr, ptr, ct.c_uint32, integer, integer, integer),
            'SDL_UpdateTexture': (integer, ptr, ptr, ptr, integer),
            'SDL_DestroyTexture': (None, ptr),
            'SDL_SetTextureBlendMode': (integer, ptr, integer),
            'SDL_ComposeCustomBlendMode': (integer, *([integer] * 6)),
            'SDL_RenderGeometryRaw': (integer, ptr, ptr, ptr, integer, ptr, integer,
                                      ptr, integer, integer, ptr, integer, integer),
        }
        for filename in candidates:
            try:
                lib = ct.CDLL(str(filename))
                for name, (result, *args) in signatures.items():
                    fn = getattr(lib, name)
                    fn.argtypes, fn.restype = args, result
                handle = lib.SDL_GetRenderer(lib.SDL_GetWindowFromID(window.id))
                if handle:
                    self.lib, self.handle = lib, handle
                    break
            except (OSError, AttributeError):
                continue
        else:
            raise RuntimeError('需要带 SDL 2.0.18 或更新版本的 Pygame 2。')

    def check(self, code):
        if code < 0:
            raise RuntimeError(self.lib.SDL_GetError().decode('utf-8', 'replace'))


class IceCanvas:
    """Cache immutable Pygame surfaces on the renderer, including generated glyphs."""
    def __init__(self, renderer, size):
        self.renderer, self.size = renderer, size
        self.textures = weakref.WeakKeyDictionary()

    def texture(self, source, additive):
        texture = self.textures.get(source)
        if texture is None:
            texture = Texture.from_surface(self.renderer, source)
            self.textures[source] = texture
        opacity = source.get_alpha()
        texture.alpha = opacity if opacity is not None else 255
        texture.blend_mode = pygame.BLENDMODE_ADD if additive else pygame.BLENDMODE_BLEND
        return texture

    def blit(self, source, dest, area=None, special_flags=0):
        additive = special_flags in (pygame.BLEND_RGB_ADD, pygame.BLEND_RGBA_ADD)
        tex = self.texture(source, additive)
        if area is None:
            w, h = source.get_size()
        else:
            w, h = pygame.Rect(area).size
        tex.draw(srcrect=area, dstrect=(int(dest[0]), int(dest[1]), w, h))

    def blit_scaled(self, source, dest_rect, additive=False):
        self.texture(source, additive).draw(dstrect=dest_rect)


def ice_atlas(cell=96):
    """Bake light kernels, cut crystal and pearl impostors into a 4×3 RGBA atlas."""
    v = ((np.arange(cell) + .5) / cell * 2 - 1).astype('f4')
    x, y = np.meshgrid(v, v)
    radius2 = x*x + y*y
    radial = np.sqrt(radius2)
    atlas = np.zeros((3*cell, 4*cell, 4), dtype=np.uint8)
    # RGB remains independent of opacity, so light outside the glass adds to the sky.
    palette = np.array([(30, 51, 81), (37, 72, 111), (106, 137, 163),
                        (216, 235, 255), (201, 228, 254), (109, 184, 255),
                        (136, 194, 250), (89, 151, 222), (0,0,0), (0,0,0),
                        (0,0,0), (164, 215, 255)], dtype='f4')
    for kind, tint in enumerate(palette):
        opacity = np.zeros_like(x)
        if kind in (8, 9, 10):
            # Light travels through the body. The Fresnel rim, reflected panels
            # and an off-axis caustic read differently from an opaque white dot.
            scale = .62
            nx, ny = x/scale, -(y-.075)/scale
            rr = nx*nx + ny*ny
            nz = np.sqrt(np.maximum(0, 1-rr))
            edge = np.clip((1-np.sqrt(rr))*cell*.32+.5,0,1)
            fresnel = (1-nz)**2.0
            if kind == 10:
                angle = np.arctan2(ny,nx)
                fold = np.cos(10*angle + 3.*nz)
                nx = nx + .095*fold
                ny = ny + .065*np.sin(10*angle + 3.*nz)
            lambert = np.clip(-.41*nx+.71*ny+.47*nz,0,1)
            gleam = np.exp(-((nx+.34)**2/.011+(ny-.42)**2/.022))
            window = np.exp(-((nx-.45)**2/.009+(ny-.16)**2/.12))
            caustic = np.exp(-((ny+.53+.17*nx)**2/.013+(nx-.12)**2/.19))
            strength = (.20, .52, .13)[kind-8]
            base = np.array(((35,109,199),(138,170,202),(45,97,149))[kind-8])
            rgb = base*(strength + .52*lambert + .14*nz)[...,None]
            rgb += (fresnel*.74+gleam*.94+window*.49+caustic*.65)[...,None]*np.array((189,220,255))
            rim = np.exp(-((np.sqrt(rr)-.94)/.040)**2)
            rgb += rim[...,None]*np.array((41,70,96))
            opacity = edge*(.56 + .35*fresnel if kind!=9 else .91+.08*fresnel)
            rgb = rgb * edge[...,None]
            collar = (np.abs(x)<.116)&(y<-.51)&(y>-.65)
            cord = (np.abs(x)<.011)&(y<-.65)&(y>-.88)
            seam = np.clip(.6+.33*np.cos(x*147),0,1)
            rgb[collar] = (seam[...,None]*np.array((133,168,201)))[collar]
            rgb[cord] = (84,119,152)
            opacity[collar | cord] = .88
            rgb += np.exp(-radius2/.40)[...,None]*np.array((3,10,21))
        else:
            light = .82*np.exp(-radius2/.109)+.26*np.exp(-radius2/.28)
            if kind in (0,1,2):
                # An elongated, faceted frost needle with a thin luminous ridge.
                body = np.clip(1-abs(x)-.88*abs(y),0,1)
                ridge = np.exp(-y*y/.025)*np.clip(1-abs(x),0,1)**.65
                light = (.56*body + .57*ridge + .17*np.exp(-radius2/.24))*(.89+.19*x)
            if kind in (3,5,11):
                light = (np.exp(-radius2/.044)+.24*np.exp(-radius2/.18)
                         +.61*np.exp(-np.minimum(abs(x),abs(y))*39.)*
                         np.maximum(0.,1-np.maximum(abs(x),abs(y)))**1.7)
            rgb = (light*np.clip((1-radial)*5,0,1))[...,None]*tint
        row, col = divmod(kind,4)
        tile = atlas[row*cell:(row+1)*cell,col*cell:(col+1)*cell]
        tile[:,:,:3] = np.clip(rgb,0,255).astype('u1')
        tile[:,:,3] = np.rint(opacity*255).astype('u1')
        tile[[0,-1],:,:] = tile[:,[0,-1],:] = 0
    return atlas


class ParticleBatch:
    def __init__(self, sdl):
        self.sdl = sdl
        lib = sdl.lib
        atlas = ice_atlas()
        height, width, _ = atlas.shape
        # SDL_PIXELFORMAT_RGBA32 is the byte order R,G,B,A on either endian.
        format_rgba32 = 0x16762004 if sys.byteorder == 'little' else 0x16462004
        self.texture = lib.SDL_CreateTexture(sdl.handle,format_rgba32,0,width,height)
        if not self.texture:
            sdl.check(-1)
        # Emissive texels carry zero opacity; glass texels attenuate what is behind.
        blend = lib.SDL_ComposeCustomBlendMode(2, 6, 1, 2, 6, 1)
        self.mixed = lib.SDL_SetTextureBlendMode(self.texture,blend) == 0
        if not self.mixed:
            # Software SDL lacks custom blending. Preserve sorted order and switch
            # between ordinary alpha glass and additive light for contiguous runs.
            cell = width//4
            for kind in range(12):
                row,col = divmod(kind,4)
                tile = atlas[row*cell:(row+1)*cell,col*cell:(col+1)*cell]
                if kind in (8,9,10):
                    alpha = np.maximum(tile[:,:,3],tile[:,:,:3].max(axis=2))
                    tile[:,:,:3] = np.clip(tile[:,:,:3]*(255./np.maximum(1,alpha)[...,None]),0,255)
                    tile[:,:,3] = alpha
                else:
                    tile[:,:,3] = 255
        sdl.check(lib.SDL_UpdateTexture(self.texture,None,atlas.ctypes.data,atlas.strides[0]))
        self.capacity = 0
        self.uv_map = np.empty((12,4,2),'f4')
        for k in range(12):
            col,row = k%4,k//4
            self.uv_map[k] = [(col/4,row/3),((col+1)/4,row/3),
                              ((col+1)/4,(row+1)/3),(col/4,(row+1)/3)]
        self.length_scale = np.array((1.78, 2.15, 1.72)+(1.,)*9,'f4')
        self.width_scale = np.array((.58, .55, .58)+(1.,)*9,'f4')
        self.extent = np.array((2.,2.1,2.3,4.3,2.4,3.5,2.3,2.2,1.61,1.61,1.61,3.4),'f4')

    def reserve(self,n):
        if n <= self.capacity:
            return
        self.capacity = max(n + 1024, 32768)
        shape = (self.capacity,4)
        self.vertices = np.empty((*shape,2),'f4')
        self.colors = np.empty((*shape,4),'u1')
        self.uv = np.empty((*shape,2),'f4')
        self.indices = (np.arange(self.capacity,dtype='i4')[:,None]*4 +
                        np.array((0,1,2,0,2,3),'i4')).ravel()

    def draw(self, projected):
        xy,depth,kind,energy,radius,axes = projected
        n = len(kind)
        if n == 0:
            return
        self.reserve(n)
        order = np.argsort(-depth,kind='stable')
        mat = kind[order]
        p = xy[order]
        extent = np.maximum(.8, radius[order]*self.extent[mat])
        verts = self.vertices[:n]
        # The long axis follows the projected 3D needle; the short axis gives it thickness.
        direction = axes[order]
        along_x = direction[:,0] * extent * self.length_scale[mat]
        along_y = direction[:,1] * extent * self.length_scale[mat]
        across_x = -direction[:,1] * extent * self.width_scale[mat]
        across_y = direction[:,0] * extent * self.width_scale[mat]
        for component, along, across in ((0,along_x,across_x),(1,along_y,across_y)):
            center = p[:,component]
            verts[:,0,component] = center-along-across
            verts[:,1,component] = center+along-across
            verts[:,2,component] = center+along+across
            verts[:,3,component] = center-along+across
        np.take(self.uv_map,mat,axis=0,out=self.uv[:n])
        gain = np.minimum(255, 255*(1.-np.exp(-1.7*energy[order]))).astype('u1')
        if self.mixed:
            self.colors[:n] = gain[:,None,None]
            self.submit(0,n)
        else:
            # Standard SDL blending already applies alpha to the source RGB.
            self.colors[:n,:,:3] = 255
            self.colors[:n,:,3] = gain[:,None]
            glass = (mat>=8)&(mat<=10)
            boundaries = np.r_[0,np.flatnonzero(glass[1:] != glass[:-1])+1,n]
            for start,stop in zip(boundaries[:-1],boundaries[1:]):
                self.sdl.lib.SDL_SetTextureBlendMode(self.texture,1 if glass[start] else 2)
                self.submit(start,stop)

    def submit(self, start, stop):
        # Rebase each contiguous range onto the reusable zero-based triangle indices.
        first = int(start)*4
        count = int(stop-start)
        ret = self.sdl.lib.SDL_RenderGeometryRaw(
            self.sdl.handle,self.texture,self.vertices.ctypes.data+first*8,8,
            self.colors.ctypes.data+first*4,4,self.uv.ctypes.data+first*8,8,
            4*count,self.indices.ctypes.data,6*count,4)
        self.sdl.check(ret)

    def close(self):
        if self.texture:
            self.sdl.lib.SDL_DestroyTexture(self.texture)
            self.texture = None


class Bloom:
    """Downsample and diffuse the scene on render targets; add the result back."""
    def __init__(self, renderer, size):
        self.renderer = renderer
        self.layers = [Texture(renderer,(max(1,size[0]//d),max(1,size[1]//d)),target=True)
                       for d in (3,9,24)]
        self.soft = [Texture(renderer,(t.width,t.height),target=True) for t in self.layers[1:]]

    def apply(self, scene):
        renderer = self.renderer
        previous = scene
        for layer in self.layers:
            renderer.target = layer
            previous.blend_mode = pygame.BLENDMODE_NONE
            previous.alpha = 255
            previous.draw(dstrect=(0,0,layer.width,layer.height))
            previous = layer
        for source,dest in zip(self.layers[1:],self.soft):
            renderer.target = dest
            renderer.draw_color = (0,0,0,255)
            renderer.clear()
            source.blend_mode = pygame.BLENDMODE_ADD
            for dx,dy,alpha in ((0,0,83),(-1,-1,43),(1,1,43),(1,-1,43),(-1,1,43)):
                source.alpha = alpha
                source.draw(dstrect=(dx,dy,source.width,source.height))
        renderer.target = scene
        for t,alpha in zip(self.soft,(53,36)):
            t.alpha = alpha
            t.blend_mode = pygame.BLENDMODE_ADD
            t.draw(dstrect=(0,0,scene.width,scene.height))


class ChristmasTree:
    def __init__(self, size=(1080,1920), fullscreen=False):
        pygame.display.init()
        pygame.font.init()
        self.size = size
        dw,dh = pygame.display.get_desktop_sizes()[0]
        fit = min(1.,(dw*.94)/size[0],(dh*.90)/size[1])
        initial = tuple(max(1,round(n*fit)) for n in size)
        self.window = Window('霜夜星愿 · Merry Christmas', initial,
                             position=WINDOWPOS_CENTERED, resizable=True)
        self.fullscreen = False
        self.renderer = Renderer(self.window, accelerated=-1, vsync=False, target_texture=True)
        self.canvas = IceCanvas(self.renderer,size)
        self.frame = Texture(self.renderer,size,target=True)
        self.sdl = SDLGeometry(self.window)
        self.particles = ParticleBatch(self.sdl)
        self.bloom = Bloom(self.renderer,size)
        self.fir = Fir()
        self.sky = WinterSky(size)
        self.lettering = IceLettering(size)
        self.topper = IceTopper()
        self.running = True
        pygame.mouse.set_visible(False)
        if fullscreen:
            self.toggle_fullscreen()
        # Prepare the star's slowly varying facets and broad glow before the clock starts.
        radius = self.fir.star_screen(0,*size)[2]
        self.renderer.target = self.frame
        for phase in np.linspace(0,math.tau,32,endpoint=False):
            self.topper.draw(self.canvas,14.+phase/.47, size[0]/2, size[1]/4, radius)
        self.renderer.target = None
        self.start = perf_counter()

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.window.set_windowed()
        else:
            self.window.set_fullscreen(desktop=True)
        self.fullscreen = not self.fullscreen

    def event(self, event):
        if event.type in (pygame.QUIT,pygame.WINDOWCLOSE):
            self.running = False
        elif event.type == pygame.KEYDOWN and not getattr(event,'repeat',False):
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif event.key == pygame.K_SPACE:
                self.start = perf_counter()

    def draw(self, t):
        self.renderer.target = self.frame
        self.sky.draw_background(self.canvas,t)
        self.particles.draw(self.fir.project(t,*self.size))
        x,y,radius,_ = self.fir.star_screen(t,*self.size)
        self.topper.draw(self.canvas,t,x,y,radius)
        self.sky.draw_snow(self.canvas,t)
        self.bloom.apply(self.frame)
        self.lettering.draw(self.canvas,t)

    def present(self):
        renderer = self.renderer
        renderer.target = None
        renderer.draw_color = (0,0,0,255)
        renderer.clear()
        w,h = self.window.size
        scale = min(w/self.size[0], h/self.size[1])
        width,height = max(1,round(self.size[0]*scale)),max(1,round(self.size[1]*scale))
        self.frame.alpha = 255
        self.frame.blend_mode = pygame.BLENDMODE_NONE
        self.frame.draw(dstrect=((w-width)//2,(h-height)//2,width,height))
        renderer.present()

    def run(self, measure_seconds=None):
        last = next_frame = self.start = perf_counter()
        begin = self.start
        intervals = []
        while self.running:
            for event in pygame.event.get():
                self.event(event)
            if not self.running:
                break
            now = perf_counter()
            self.draw(now-self.start)
            self.present()
            if measure_seconds is not None:
                if now-begin > .5:
                    intervals.append(now-last)
                if now-begin >= measure_seconds:
                    ms = np.array(intervals)*1000
                    print(f'{self.size[0]}×{self.size[1]} · {1000/ms.mean():.2f} FPS · '
                          f'P95 帧间隔 {np.percentile(ms,95):.2f} ms',flush=True)
                    break
            last = now
            next_frame = max(now,next_frame+1/60)
            delay = next_frame-perf_counter()
            if delay > 0:
                sleep(delay)

    def close(self):
        self.renderer.target = None
        self.particles.close()
        self.canvas.textures.clear()
        self.bloom = self.frame = self.canvas = None
        self.renderer = None
        self.window.destroy()


def main():
    parser = argparse.ArgumentParser(description='霜夜星愿 · 立体粒子圣诞树')
    parser.add_argument('--size',default='1080x1920',help='内部渲染尺寸，默认 1080x1920')
    parser.add_argument('--fullscreen', action='store_true',help='启动时全屏')
    parser.add_argument('--benchmark', type=float,metavar='SECONDS',help='测量正常播放帧率并自动退出')
    args = parser.parse_args()
    try:
        size = tuple(int(i) for i in args.size.lower().split('x'))
        if len(size) != 2 or min(size) < 160:
            raise ValueError
    except ValueError:
        parser.error('请使用 WIDTHxHEIGHT，例如 1080x1920，每边至少 160 像素')
    if args.benchmark is not None and not 2 <= args.benchmark <= 600:
        parser.error('测量时间应为 2 至 600 秒')
    show = None
    try:
        show = ChristmasTree(size,args.fullscreen)
        print(f'霜夜星愿 · {size[0]}×{size[1]} · 空格重播 / F11 全屏 / Esc 退出',flush=True)
        show.run(args.benchmark)
    except (RuntimeError,pygame.error,OSError) as exc:
        print(f'启动或渲染失败：{exc}',file=sys.stderr)
        return 1
    finally:
        if show:
            show.close()
        pygame.quit()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
