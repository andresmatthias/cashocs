"""
Created on 25/08/2020, 14.36

@author: blauths
"""

from fenics import *
import cestrel
import numpy as np



config = cestrel.create_config('./config.ini')
mesh, subdomains, boundaries, dx, ds, dS = cestrel.regular_mesh(10)
V = FunctionSpace(mesh, 'CG', 1)

y = Function(V)
p = Function(V)
u = Function(V)
u_orig = Function(V)
u_orig.vector()[:] = u.vector()[:]

F = inner(grad(y), grad(p))*dx - u*p*dx
bcs = cestrel.create_bcs_list(V, Constant(0), boundaries, [1, 2, 3, 4])

y_d = Expression('sin(2*pi*x[0])*sin(2*pi*x[1])', degree=1)
alpha = 1e-6
J = Constant(0.5)*(y - y_d)*(y - y_d)*dx + Constant(0.5*alpha)*u*u*dx

ocp = cestrel.OptimalControlProblem(F, bcs, J, y, u, p, config)

cestrel.verification.taylor_tests.control_gradient_test(ocp, [u_orig])


# Ju = ocp.reduced_cost_functional.evaluate()
# dJu = ocp.compute_gradient()[0]
#
# h = Function(V)
# h.vector()[:] = np.random.rand(V.dim())
#
# dJ_h = ocp.form_handler.scalar_product([dJu], [h])
#
# epsilons = [0.01 / 2**i for i in range(4)]
# residuals = []
#
# for eps in epsilons:
# 	u.vector()[:] = u_orig.vector()[:] + eps * h.vector()[:]
# 	ocp.state_problem.has_solution = False
# 	Jv = ocp.reduced_cost_functional.evaluate()
#
# 	res = abs(Jv - Ju - eps*dJ_h)
# 	residuals.append(res)
#
#
# def convergence_rates(E_values, eps_values, show=True):
# 	from numpy import log
# 	r = []
# 	for i in range(1, len(eps_values)):
# 		r.append(log(E_values[i] / E_values[i - 1])
#                  / log(eps_values[i] / eps_values[i - 1]))
# 	if show:
# 		print("Computed convergence rates: {}".format(r))
# 	return r
#
# convergence_rates(residuals, epsilons)
