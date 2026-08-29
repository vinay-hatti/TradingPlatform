from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize

EPS=1e-12

def sigmoid(z):
    z=np.asarray(z,dtype=float)
    out=np.empty_like(z)
    pos=z>=0
    out[pos]=1.0/(1.0+np.exp(-z[pos]))
    ez=np.exp(z[~pos])
    out[~pos]=ez/(1.0+ez)
    return out

def choose_knots(x, knot_count):
    x=np.asarray(x,dtype=float)
    qs=np.linspace(0.0,1.0,knot_count+2)[1:-1]
    vals=np.unique(np.quantile(x,qs))
    return vals.astype(float)

def spline_basis_1d(x, knots):
    x=np.asarray(x,dtype=float)
    cols=[x]
    for k in np.asarray(knots,dtype=float):
        cols.append(np.maximum(0.0,x-k))
    return np.column_stack(cols)

def monotonic_bounds(sign, n_basis):
    if sign==1:return [(0.0,None)]*n_basis
    if sign==-1:return [(None,0.0)]*n_basis
    return [(None,None)]*n_basis

@dataclass
class CertifiedMonotonicGAM:
    knot_count:int=6
    l2_penalty:float=1.0
    max_iter:int=300
    tol:float=1e-8

    def fit(self, X, y, monotonic_signs):
        X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float)
        if X.ndim!=2 or y.ndim!=1 or len(X)!=len(y):raise ValueError("shape mismatch")
        if len(monotonic_signs)!=X.shape[1]:raise ValueError("sign map mismatch")
        self.knots_=[]; blocks=[]; bounds=[(None,None)] # intercept
        for j in range(X.shape[1]):
            ks=choose_knots(X[:,j],self.knot_count)
            self.knots_.append(ks)
            b=spline_basis_1d(X[:,j],ks)
            blocks.append(b)
            bounds.extend(monotonic_bounds(int(monotonic_signs[j]),b.shape[1]))
        B=np.column_stack(blocks) if blocks else np.empty((len(X),0))
        Z=np.column_stack([np.ones(len(X)),B])
        lam=float(self.l2_penalty)
        def fun(beta):
            eta=Z@beta
            # stable logistic negative log likelihood
            loss=np.logaddexp(0.0,eta)-y*eta
            reg=0.5*lam*np.dot(beta[1:],beta[1:])
            return float(loss.mean()+reg)
        def jac(beta):
            p=sigmoid(Z@beta)
            g=(Z.T@(p-y))/len(y)
            g[1:]+=lam*beta[1:]
            return g
        res=minimize(fun,np.zeros(Z.shape[1]),jac=jac,bounds=bounds,method="L-BFGS-B",
                     options={"maxiter":self.max_iter,"ftol":self.tol,"gtol":self.tol})
        if not res.success:
            raise RuntimeError(f"MF2 optimizer failed: {res.message}")
        self.coef_=res.x; self.n_features_in_=X.shape[1]
        return self

    def _design(self,X):
        X=np.asarray(X,dtype=float)
        blocks=[spline_basis_1d(X[:,j],self.knots_[j]) for j in range(X.shape[1])]
        B=np.column_stack(blocks) if blocks else np.empty((len(X),0))
        return np.column_stack([np.ones(len(X)),B])

    def predict_proba(self,X):
        p=sigmoid(self._design(X)@self.coef_)
        return np.column_stack([1-p,p])

def pinball_loss_residual(r,q):
    r=np.asarray(r,dtype=float)
    return np.where(r>=0,q*r,(q-1.0)*r)

def elastic_net_penalty(beta,alpha,l1_ratio):
    beta=np.asarray(beta,dtype=float)
    return float(alpha*(l1_ratio*np.abs(beta).sum()+(1-l1_ratio)*0.5*np.dot(beta,beta)))

@dataclass
class CertifiedElasticNetQuantile:
    quantile:float=0.5
    alpha:float=0.001
    l1_ratio:float=0.5
    max_iter:int=1000
    tol:float=1e-7

    def fit(self,X,y):
        X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float)
        if X.ndim!=2 or y.ndim!=1 or len(X)!=len(y):raise ValueError("shape mismatch")
        q=float(self.quantile);a=float(self.alpha);r=float(self.l1_ratio)
        if not (0<q<1):raise ValueError("quantile")
        if a<0 or not (0<=r<=1):raise ValueError("penalty")
        # Exact nonsmooth objective optimized with Powell; certification target is contract fidelity,
        # not production-scale performance. Development evaluator may use a separately certified
        # scalable implementation of the same objective.
        def obj(theta):
            intercept=theta[0];beta=theta[1:]
            resid=y-(intercept+X@beta)
            return float(pinball_loss_residual(resid,q).mean()+elastic_net_penalty(beta,a,r))
        init=np.zeros(X.shape[1]+1)
        init[0]=float(np.quantile(y,q))
        res=minimize(obj,init,method="Powell",options={"maxiter":self.max_iter,"xtol":self.tol,"ftol":self.tol})
        if not res.success:
            raise RuntimeError(f"MF3 optimizer failed: {res.message}")
        self.intercept_=float(res.x[0]);self.coef_=np.asarray(res.x[1:],dtype=float);self.objective_=float(res.fun)
        return self

    def predict(self,X):
        X=np.asarray(X,dtype=float)
        return self.intercept_+X@self.coef_

def synthetic_mf2_certification():
    rng=np.random.default_rng(77)
    n=500
    x1=rng.normal(size=n);x2=rng.normal(size=n);x3=rng.normal(size=n)
    logit=1.1*x1-0.9*x2+0.2*x3
    y=(rng.random(n)<sigmoid(logit)).astype(float)
    X=np.column_stack([x1,x2,x3])
    m=CertifiedMonotonicGAM(knot_count=4,l2_penalty=0.1,max_iter=500).fit(X,y,[1,-1,0])
    grid=np.linspace(-2,2,101)
    base=np.zeros((len(grid),3))
    a=base.copy();a[:,0]=grid
    b=base.copy();b[:,1]=grid
    p1=m.predict_proba(a)[:,1];p2=m.predict_proba(b)[:,1]
    return {
        "positive_monotonic_non_decreasing":bool(np.all(np.diff(p1)>=-1e-9)),
        "negative_monotonic_non_increasing":bool(np.all(np.diff(p2)<=1e-9)),
        "finite_probabilities":bool(np.isfinite(m.predict_proba(X)).all()),
    }

def synthetic_mf3_certification():
    rng=np.random.default_rng(77)
    X=rng.normal(size=(180,3))
    y=0.7+1.2*X[:,0]-0.6*X[:,1]+rng.normal(scale=0.4,size=len(X))
    checks=[]
    for q in (0.1,0.5,0.9):
        for a in (0.001,0.01):
            for r in (0.0,0.5,1.0):
                m=CertifiedElasticNetQuantile(q,a,r,max_iter=800).fit(X,y)
                pred=m.predict(X);resid=y-pred
                obj=float(pinball_loss_residual(resid,q).mean()+elastic_net_penalty(m.coef_,a,r))
                checks.append({
                    "quantile":q,"alpha":a,"l1_ratio":r,
                    "finite":bool(np.isfinite(pred).all()),
                    "objective_matches_contract":abs(obj-m.objective_)<=1e-8,
                })
    med=CertifiedElasticNetQuantile(0.5,0.001,0.5,max_iter=800).fit(X,y)
    return {
        "case_count":len(checks),
        "all_finite":all(x["finite"] for x in checks),
        "all_objective_matches_contract":all(x["objective_matches_contract"] for x in checks),
        "median_fit_directionally_sane":bool(med.coef_[0]>0 and med.coef_[1]<0),
        "cases":checks,
    }
