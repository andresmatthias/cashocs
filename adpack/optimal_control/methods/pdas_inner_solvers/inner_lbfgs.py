"""
Created on 01.04.20, 14:22

@author: sebastian
"""

import fenics
import numpy as np
from ...optimization_algorithm import OptimizationAlgorithm
from .unconstrained_line_search import UnconstrainedLineSearch
from _collections import deque



class InnerLBFGS(OptimizationAlgorithm):

	def __init__(self, optimization_problem):
		OptimizationAlgorithm.__init__(self, optimization_problem)

		self.line_search = UnconstrainedLineSearch(self)
		self.maximum_iterations = self.config.getint('OptimizationRoutine', 'maximum_iterations_inner_pdas')
		self.tolerance = self.config.getfloat('OptimizationRoutine', 'pdas_inner_tolerance')
		self.reduced_gradient = [fenics.Function(self.optimization_problem.control_spaces[j]) for j in range(len(self.controls))]
		self.first_gradient_norm = 1.0
		self.first_iteration = True

		self.temp = [fenics.Function(V) for V in self.optimization_problem.control_spaces]
		self.storage_y = [fenics.Function(V) for V in self.optimization_problem.control_spaces]
		self.storage_s = [fenics.Function(V) for V in self.optimization_problem.control_spaces]

		self.memory_vectors = self.config.getint('OptimizationRoutine', 'memory_vectors')
		self.use_bfgs_scaling = self.config.getboolean('OptimizationRoutine', 'use_bfgs_scaling')

		if self.memory_vectors > 0:
			self.history_s = deque()
			self.history_y = deque()
			self.history_rho = deque()
			self.gradients_prev = [fenics.Function(V) for V in self.optimization_problem.control_spaces]



	def compute_search_direction(self, grad, idx_active):

		if self.memory_vectors > 0 and len(self.history_s) > 0:
			history_alpha = deque()
			for j in range(len(self.controls)):
				self.search_directions[j].vector()[:] = grad[j].vector()[:]
				self.search_directions[j].vector()[idx_active[j]] = 0.0

			for i, _ in enumerate(self.history_s):
				alpha = self.history_rho[i]*self.form_handler.scalar_product(self.history_s[i], self.search_directions)
				history_alpha.append(alpha)
				for j in range(len(self.controls)):
					self.search_directions[j].vector()[:] -= alpha*self.history_y[i][j].vector()[:]

			if self.use_bfgs_scaling and self.iteration > 0:
				factor = self.form_handler.scalar_product(self.history_y[0], self.history_s[0]) / self.form_handler.scalar_product(self.history_y[0], self.history_y[0])
			else:
				factor = 1.0

			for j in range(len(self.controls)):
				self.search_directions[j].vector()[:] *= factor
				self.search_directions[j].vector()[idx_active[j]] = 0.0

			for i, _ in enumerate(self.history_s):
				beta = self.history_rho[-1 - i]*self.form_handler.scalar_product(self.history_y[-1 - i], self.search_directions)

				for j in range(len(self.controls)):
					self.search_directions[j].vector()[:] += self.history_s[-1 - i][j].vector()[:]*(history_alpha[-1 - i] - beta)

			for j in range(len(self.controls)):
				self.search_directions[j].vector()[idx_active[j]] = 0.0
				self.search_directions[j].vector()[:] *= -1

		else:
			for j in range(len(self.controls)):
				self.search_directions[j].vector()[:] = - grad[j].vector()[:]
				self.search_directions[j].vector()[idx_active[j]] = 0.0

		return self.search_directions



	def run(self, idx_active):

		self.iteration = 0
		self.relative_norm = 1.0
		self.state_problem.has_solution = False

		self.adjoint_problem.has_solution = False
		self.gradient_problem.has_solution = False
		self.gradient_problem.solve()

		for j in range(len(self.controls)):
			self.reduced_gradient[j].vector()[:] = self.gradients[j].vector()[:]
			self.reduced_gradient[j].vector()[idx_active[j]] = 0.0

		self.gradient_norm = np.sqrt(self.form_handler.scalar_product(self.reduced_gradient, self.reduced_gradient))
		self.gradient_norm_initial = self.gradient_norm

		if self.first_iteration:
			self.first_gradient_norm = self.gradient_norm_initial
			self.first_iteration = False

		while not (self.gradient_norm <= self.atol + self.rtol*self.gradient_norm_initial or self.relative_norm*self.gradient_norm_initial/self.first_gradient_norm <= self.tolerance/2):
			self.search_directions = self.compute_search_direction(self.reduced_gradient, idx_active)

			self.directional_derivative = self.form_handler.scalar_product(self.search_directions, self.reduced_gradient)
			if self.directional_derivative > 0:
				print('No descent direction found')
				for j in range(self.form_handler.control_dim):
					self.search_directions[j].vector()[:] = -self.reduced_gradient[j].vector()[:]

			self.line_search.search(self.search_directions)
			if self.line_search_broken:
				if self.soft_exit:
					print('Armijo rule failed.')
					break
				else:
					raise SystemExit('Armijo rule failed.')

			if self.memory_vectors > 0:
				for i in range(len(self.controls)):
					self.gradients_prev[i].vector()[:] = self.reduced_gradient[i].vector()[:]

			self.adjoint_problem.has_solution = False
			self.gradient_problem.has_solution = False
			self.gradient_problem.solve()

			for j in range(len(self.controls)):
				self.reduced_gradient[j].vector()[:] = self.gradients[j].vector()[:]
				self.reduced_gradient[j].vector()[idx_active[j]] = 0.0

			self.gradient_norm = np.sqrt(self.form_handler.scalar_product(self.reduced_gradient, self.reduced_gradient))

			self.relative_norm = self.gradient_norm / self.gradient_norm_initial

			if self.memory_vectors > 0:
				for i in range(len(self.controls)):
					self.storage_y[i].vector()[:] = self.reduced_gradient[i].vector()[:] - self.gradients_prev[i].vector()[:]
					self.storage_s[i].vector()[:] = self.stepsize*self.search_directions[i].vector()[:]

				self.history_y.appendleft([x.copy(True) for x in self.storage_y])
				self.history_s.appendleft([x.copy(True) for x in self.storage_s])
				rho = 1/self.form_handler.scalar_product(self.storage_y, self.storage_s)
				self.history_rho.appendleft(rho)

				if 1/rho <= 0:
					self.history_s = deque()
					self.history_y = deque()
					self.history_rho = deque()

				if len(self.history_s) > self.memory_vectors:
					self.history_s.pop()
					self.history_y.pop()
					self.history_rho.pop()

			self.iteration += 1
			if self.iteration >= self.maximum_iterations:
				self.print_results()
				if self.soft_exit:
					print('Maximum number of iterations exceeded.')
					break
				else:
					raise SystemExit('Maximum number of iterations exceeded.')
