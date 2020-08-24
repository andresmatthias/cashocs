"""
Created on 15/06/2020, 08.10

@author: blauths
"""

import fenics
from ..utils import _solve_linear_problem



class ShapeGradientProblem:
	"""Riesz problem for the computation of the shape gradient.

	"""

	def __init__(self, shape_form_handler, state_problem, adjoint_problem):
		"""Initialize the ShapeGradientProblem.

		Parameters
		----------
		shape_form_handler : cestrel._forms.ShapeFormHandler
			The ShapeFormHandler object corresponding to the shape optimization problem.
		state_problem : cestrel._pde_problems.StateProblem
			The corresponding state problem.
		adjoint_problem : cestrel._pde_problems.AdjointProblem
			The corresponding adjoint problem.
		"""

		self.shape_form_handler = shape_form_handler
		self.state_problem = state_problem
		self.adjoint_problem = adjoint_problem

		self.gradient = fenics.Function(self.shape_form_handler.deformation_space)
		self.gradient_norm_squared = 1.0

		self.config = self.shape_form_handler.config

		self.has_solution = False



	def solve(self):
		"""Solves the Riesz projection problem to obtain the shape gradient of the cost functional.

		Returns
		-------
		gradient : dolfin.function.function.Function
			The function representing the shape gradient of the (reduced) cost functional.
		"""

		self.state_problem.solve()
		self.adjoint_problem.solve()

		if not self.has_solution:

			self.shape_form_handler.regularization.update_geometric_quantities()
			self.shape_form_handler.assembler.assemble(self.shape_form_handler.fe_shape_derivative_vector)
			b = fenics.as_backend_type(self.shape_form_handler.fe_shape_derivative_vector).vec()
			_solve_linear_problem(self.shape_form_handler.ksp, self.shape_form_handler.scalar_product_matrix, b, self.gradient.vector().vec())

			self.has_solution = True

			self.gradient_norm_squared = self.shape_form_handler.scalar_product(self.gradient, self.gradient)

		return self.gradient
