"""Mesh generation and import tools.

This module consists of tools for for the fast generation
or import of meshes into fenics. The import_mesh function
is used to import (converted) gmsh mesh files, and the
regular_(box_)mesh commands create 2D and 3D box meshes
which are great for testing.
"""

import fenics
from ufl import Jacobian, JacobianInverse
import numpy as np
import time
from petsc4py import PETSc
import os
import sys
import configparser
from .utils import _setup_petsc_options, write_out_mesh, _assemble_petsc_system
import warnings
import json



def import_mesh(arg):
	"""Imports a mesh file for use with cestrel / fenics.

	This function imports a mesh file that was generated by GMSH and converted to
	.xdmf with the command line function mesh-convert (see cestrel main documentation).
	The syntax for the conversion is
		mesh-convert in.msh out.xdmf
	If there are Physical quantities specified in the gmsh file, these are imported
	to the subdomains and boundaries output of this function and can also be directly
	accessed via the measures, e.g., with dx(1), ds(1), etc.

	Parameters
	----------
	arg : str or configparser.ConfigParser
		This is either a string, in which case it corresponds to the location
		of the mesh file in .xdmf file format, or a config file that
		has this path stored in its settings.

	Returns
	-------
	mesh : dolfin.cpp.mesh.Mesh
		The imported (computational) mesh.
	subdomains : dolfin.cpp.mesh.MeshFunctionSizet
		A MeshFunction object containing the subdomains,
		i.e., the Physical regions marked in the gmsh
		file.
	boundaries : dolfin.cpp.mesh.MeshFunctionSizet
		A MeshFunction object containing the boundaries,
		i.e., the Physical regions marked in the gmsh
		file. Can be, e.g., used to set up boundary
		conditions.
	dx : ufl.measure.Measure
		The volume measure of the mesh corresponding to
		the subdomains (i.e. gmsh Physical region indices).
	ds : ufl.measure.Measure
		The surface measure of the mesh corresponding to
		the boundaries (i.e. gmsh Physical region indices).
	dS : ufl.measure.Measure
		The interior facet measure of the mesh corresponding
		to boundaries (i.e. gmsh Physical region indices).
	"""
	
	start_time = time.time()
	print('Importing mesh to FEniCS')
	# Check for the file format

	if type(arg) == str:
		mesh_file = arg
		mesh_attribute = 'str'
	elif type(arg) == configparser.ConfigParser:
		mesh_attribute = 'config'
		### overloading for remeshing
		if not arg.getboolean('Mesh', 'remesh', fallback=False):
			mesh_file = arg.get('Mesh', 'mesh_file')
		else:
			if not '_cestrel_remesh_flag' in sys.argv:
				mesh_file = arg.get('Mesh', 'mesh_file')
			else:
				temp_dir = sys.argv[-1]
				with open(temp_dir + '/temp_dict.json', 'r') as file:
					temp_dict = json.load(file)
				mesh_file = temp_dict['mesh_file']

	else:
		raise Exception('Not a valid input for import_mesh')

	if mesh_file[-5:] == '.xdmf':
		file_string = mesh_file[:-5]
	else:
		raise Exception('Not a suitable mesh file format')
	
	mesh = fenics.Mesh()
	xdmf_file = fenics.XDMFFile(mesh.mpi_comm(), mesh_file)
	xdmf_file.read(mesh)
	xdmf_file.close()
	
	subdomains_mvc = fenics.MeshValueCollection('size_t', mesh, mesh.geometric_dimension())
	boundaries_mvc = fenics.MeshValueCollection('size_t', mesh, mesh.geometric_dimension() - 1)

	if os.path.exists(file_string + '_subdomains.xdmf'):
		xdmf_subdomains = fenics.XDMFFile(mesh.mpi_comm(), file_string + '_subdomains.xdmf')
		xdmf_subdomains.read(subdomains_mvc, 'subdomains')
		xdmf_subdomains.close()
	if os.path.exists(file_string + '_boundaries.xdmf'):
		xdmf_boundaries = fenics.XDMFFile(mesh.mpi_comm(), file_string + '_boundaries.xdmf')
		xdmf_boundaries.read(boundaries_mvc, 'boundaries')
		xdmf_boundaries.close()

	subdomains = fenics.MeshFunction('size_t', mesh, subdomains_mvc)
	boundaries = fenics.MeshFunction('size_t', mesh, boundaries_mvc)

	dx = fenics.Measure('dx', domain=mesh, subdomain_data=subdomains)
	ds = fenics.Measure('ds', domain=mesh, subdomain_data=boundaries)
	dS = fenics.Measure('dS', domain=mesh, subdomain_data=boundaries)
	
	end_time = time.time()
	print('Done Importing Mesh. Elapsed Time: ' + format(end_time - start_time, '.3e') + ' s')
	print('')

	# Add an attribute to the mesh to show with what procedure it was generated
	mesh._cestrel_generator = mesh_attribute

	return mesh, subdomains, boundaries, dx, ds, dS



def regular_mesh(n=10, L_x=1.0, L_y=1.0, L_z=None):
	r"""Creates a mesh corresponding to a rectangle or cube.

	This function creates a uniform mesh of either a rectangle
	or a cube, starting at the origin and having length specified
	in lx, lx, lz. The resulting mesh uses n elements along the
	shortest direction and accordingly many along the longer ones.
	The resulting domain is
		$$[0, L_x] \times [0, L_y] \phantom{ \times [0, L_z] a} \quad \text{ in } 2D, \\
		[0, L_x] \times [0, L_y] \times [0, L_z] \quad \text{ in } 3D.
		$$

	The boundary markers are ordered as follows:

	  - 1 corresponds to \(\{x=0\}\)

	  - 2 corresponds to \(\{x=L_x\}\)

	  - 3 corresponds to \(\{y=0\}\)

	  - 4 corresponds to \(\{y=L_y\}\)

	  - 5 corresponds to \(\{z=0\}\) (only in 3D)

	  - 6 corresponds to \(\{z=L_z\}\) (only in 3D)

	Parameters
	----------
	n : int
		Number of elements in the shortest coordinate direction.
	L_x : float
		Length in x-direction.
	L_y : float
		Length in y-direction.
	L_z : float or None, optional
		Length in z-direction, if this is None, then the geometry
		will be two-dimensional (default is None).

	Returns
	-------
	mesh : dolfin.cpp.mesh.Mesh
		The computational mesh.
	subdomains : dolfin.cpp.mesh.MeshFunctionSizet
		A MeshFunction object containing the subdomains.
	boundaries : dolfin.cpp.mesh.MeshFunctionSizet
		A MeshFunction object containing the boundaries.
	dx : ufl.measure.Measure
		The volume measure of the mesh corresponding to subdomains.
	ds : ufl.measure.Measure
		The surface measure of the mesh corresponding to boundaries.
	dS : ufl.measure.Measure
		The interior facet measure of the mesh corresponding to boundaries.
	"""

	n = int(n)
	
	if L_z is None:
		sizes = [L_x, L_y]
		dim = 2
	else:
		sizes = [L_x, L_y, L_z]
		dim = 3
	
	size_min = np.min(sizes)
	num_points = [int(np.round(length/size_min*n)) for length in sizes]
	
	if L_z is None:
		mesh = fenics.RectangleMesh(fenics.Point(0, 0), fenics.Point(sizes), num_points[0], num_points[1])
	else:
		mesh = fenics.BoxMesh(fenics.Point(0, 0, 0), fenics.Point(sizes), num_points[0], num_points[1], num_points[2])
	
	subdomains = fenics.MeshFunction('size_t', mesh, dim=dim)
	boundaries = fenics.MeshFunction('size_t', mesh, dim=dim - 1)
	
	x_min = fenics.CompiledSubDomain('on_boundary && near(x[0], 0, tol)', tol=fenics.DOLFIN_EPS)
	x_max = fenics.CompiledSubDomain('on_boundary && near(x[0], length, tol)', tol=fenics.DOLFIN_EPS, length=sizes[0])
	x_min.mark(boundaries, 1)
	x_max.mark(boundaries, 2)

	y_min = fenics.CompiledSubDomain('on_boundary && near(x[1], 0, tol)', tol=fenics.DOLFIN_EPS)
	y_max = fenics.CompiledSubDomain('on_boundary && near(x[1], length, tol)', tol=fenics.DOLFIN_EPS, length=sizes[1])
	y_min.mark(boundaries, 3)
	y_max.mark(boundaries, 4)

	if L_z is not None:
		z_min = fenics.CompiledSubDomain('on_boundary && near(x[2], 0, tol)', tol=fenics.DOLFIN_EPS)
		z_max = fenics.CompiledSubDomain('on_boundary && near(x[2], length, tol)', tol=fenics.DOLFIN_EPS, length=sizes[2])
		z_min.mark(boundaries, 5)
		z_max.mark(boundaries, 6)
	
	dx = fenics.Measure('dx', mesh, subdomain_data=subdomains)
	ds = fenics.Measure('ds', mesh, subdomain_data=boundaries)
	dS = fenics.Measure('dS', mesh)
	
	return mesh, subdomains, boundaries, dx, ds, dS



def regular_box_mesh(n=10, S_x=0.0, S_y=0.0, S_z=None, E_x=1.0, E_y=1.0, E_z=None):
	r"""Creates a mesh corresponding to a rectangle or cube.

	This function creates a uniform mesh of either a rectangle
	or a cube, with specified start (S_) and end points (E_).
	The resulting mesh uses n elements along the shortest direction
	and accordingly many along the longer ones. The resulting domain is
		$$[S_x, E_x] \times [S_y, E_y] \phantom{ \times [S_z, E_z] a} \quad \text{ in } 2D, \\
		[S_x, E_x] \times [S_y, E_y] \times [S_z, E_z] \quad \text{ in } 3D.
		$$

	The boundary markers are ordered as follows:

	  - 1 corresponds to \(\{x=S_x\}\)

	  - 2 corresponds to \(\{x=E_x\}\)

	  - 3 corresponds to \(\{y=S_y\}\)

	  - 4 corresponds to \(\{y=E_y\}\)

	  - 5 corresponds to \(\{z=S_z\}\) (only in 3D)

	  - 6 corresponds to \(\{z=E_z\}\) (only in 3D)

	Parameters
	----------
	n : int
		Number of elements in the shortest coordinate direction.
	S_x : float
		Start of the x-interval.
	S_y : float
		Start of the y-interval.
	S_z : float or None, optional
		Start of the z-interval, mesh is 2D if this is None
		(default is None).
	E_x : float
		End of the x-interval.
	E_y : float
		End of the y-interval.
	E_z : float or None, optional
		End of the z-interval, mesh is 2D if this is None
		(default is None).

	Returns
	-------
	mesh : dolfin.cpp.mesh.Mesh
		the computational mesh
	subdomains : dolfin.cpp.mesh.MeshFunctionSizet
		a MeshFunction object containing the subdomains
	boundaries : dolfin.cpp.mesh.MeshFunctionSizet
		a MeshFunction object containing the boundaries
	dx : ufl.measure.Measure
		the volume measure of the mesh corresponding to subdomains
	ds : ufl.measure.Measure
		the surface measure of the mesh corresponding to boundaries
	dS : ufl.measure.Measure
		the interior facet measure of the mesh corresponding to boundaries
	"""

	n = int(n)

	assert S_x < E_x, 'Incorrect input for the x-coordinate'
	assert S_y < E_y, 'Incorrect input for the y-coordinate'
	assert (S_z is None and E_z is None) or (S_z < E_z), 'Incorrect input for the z-coordinate'

	if S_z is None:
		lx = E_x - S_x
		ly = E_y - S_y
		sizes = [lx, ly]
		dim = 2
	else:
		lx = E_x - S_x
		ly = E_y - S_y
		lz = E_z - S_z
		sizes = [lx, ly, lz]
		dim = 3

	size_min = np.min(sizes)
	num_points = [int(np.round(length/size_min*n)) for length in sizes]

	if S_z is None:
		mesh = fenics.RectangleMesh(fenics.Point(S_x, S_y), fenics.Point(E_x, E_y), num_points[0], num_points[1])
	else:
		mesh = fenics.BoxMesh(fenics.Point(S_x, S_y, S_z), fenics.Point(E_x, E_y, E_z), num_points[0], num_points[1], num_points[2])

	subdomains = fenics.MeshFunction('size_t', mesh, dim=dim)
	boundaries = fenics.MeshFunction('size_t', mesh, dim=dim - 1)

	x_min = fenics.CompiledSubDomain('on_boundary && near(x[0], sx, tol)', tol=fenics.DOLFIN_EPS, sx=S_x)
	x_max = fenics.CompiledSubDomain('on_boundary && near(x[0], ex, tol)', tol=fenics.DOLFIN_EPS, ex=E_x)
	x_min.mark(boundaries, 1)
	x_max.mark(boundaries, 2)

	y_min = fenics.CompiledSubDomain('on_boundary && near(x[1], sy, tol)', tol=fenics.DOLFIN_EPS, sy=S_y)
	y_max = fenics.CompiledSubDomain('on_boundary && near(x[1], ey, tol)', tol=fenics.DOLFIN_EPS, ey=E_y)
	y_min.mark(boundaries, 3)
	y_max.mark(boundaries, 4)

	if S_z is not None:
		z_min = fenics.CompiledSubDomain('on_boundary && near(x[2], sz, tol)', tol=fenics.DOLFIN_EPS, sz=S_z)
		z_max = fenics.CompiledSubDomain('on_boundary && near(x[2], ez, tol)', tol=fenics.DOLFIN_EPS, ez=E_z)
		z_min.mark(boundaries, 5)
		z_max.mark(boundaries, 6)

	dx = fenics.Measure('dx', mesh, subdomain_data=subdomains)
	ds = fenics.Measure('ds', mesh, subdomain_data=boundaries)
	dS = fenics.Measure('dS', mesh)

	return mesh, subdomains, boundaries, dx, ds, dS





class _MeshHandler:
	"""Handles the mesh for shape optimization problems.

	This class implements all mesh related things for the shape optimization,
	 such as transformations and remeshing. Also includes mesh quality control
	 checks.
	"""

	def __init__(self, shape_optimization_problem):
		"""Initializes the MeshHandler object.

		Parameters
		----------
		shape_optimization_problem : cestrel._shape_optimization.shape_optimization_problem.ShapeOptimizationProblem
			The corresponding shape optimization problem.
		"""

		self.shape_optimization_problem = shape_optimization_problem
		self.shape_form_handler = self.shape_optimization_problem.shape_form_handler
		# Namespacing
		self.mesh = self.shape_form_handler.mesh
		self.dx = self.shape_form_handler.dx
		self.bbtree = self.mesh.bounding_box_tree()
		self.config = self.shape_form_handler.config

		self.volume_change = float(self.config.get('MeshQuality', 'volume_change', fallback='inf'))
		self.angle_change = float(self.config.get('MeshQuality', 'angle_change', fallback='inf'))

		self.radius_ratios_initial_mf = fenics.MeshQuality.radius_ratios(self.mesh)
		self.radius_ratios_initial = self.radius_ratios_initial_mf.array().copy()

		self.mesh_quality_tol_lower = self.config.getfloat('MeshQuality', 'tol_lower', fallback=0.05)
		self.mesh_quality_tol_upper =  self.config.getfloat('MeshQuality', 'tol_upper', fallback=0.1)
		assert self.mesh_quality_tol_lower < self.mesh_quality_tol_upper, \
			'The lower remeshing tolerance has to be strictly smaller than the upper remeshing tolerance'
		if self.mesh_quality_tol_lower > 0.9*self.mesh_quality_tol_upper:
			warnings.warn('You are using a lower remesh tolerance close to the upper one. This may slow down the optimization considerably.')

		self.mesh_quality_measure = self.config.get('MeshQuality', 'measure', fallback='skewness')
		assert self.mesh_quality_measure in ['skewness', 'maximum_angle', 'radius_ratios', 'condition_number'], \
			'MeshQuality measure has to be one of `skewness`, `maximum_angle`, `condition_number`, or `radius_ratios`.'

		self.mesh_quality_type = self.config.get('MeshQuality', 'type', fallback='min')
		assert self.mesh_quality_type in ['min', 'minimum', 'avg', 'average'], \
			'MeshQuality type has to be one of `min`, `minimum`, `avg`, or `average`.'

		self.current_mesh_quality = 1.0
		self.compute_mesh_quality()

		self.__setup_decrease_computation()
		self.__setup_a_priori()

		# Remeshing initializations
		self.do_remesh = self.config.getboolean('Mesh', 'remesh', fallback=False)

		if self.do_remesh:
			self.temp_dict = self.shape_optimization_problem.temp_dict
			self.remesh_counter = self.temp_dict.get('remesh_counter', 0)
			self.gmsh_file = self.temp_dict['gmsh_file']
			assert self.gmsh_file[-4:] == '.msh', 'Not a valid gmsh file'
			self.mesh_directory = os.path.dirname(os.path.realpath(self.config.get('Mesh', 'gmsh_file')))

			self.remesh_directory = self.mesh_directory + '/cestrel_remesh'
			if not os.path.exists(self.remesh_directory):
				os.mkdir(self.remesh_directory)
			if not '_cestrel_remesh_flag' in sys.argv:
				os.system('rm -r ' + self.remesh_directory + '/*')
			self.remesh_geo_file = self.remesh_directory + '/remesh.geo'

		# create a copy of the initial mesh file
		if self.do_remesh and self.remesh_counter == 0:
			self.gmsh_file_init = self.remesh_directory + '/mesh_' + format(self.remesh_counter, 'd') + '.msh'
			copy_mesh = 'cp ' + self.gmsh_file + ' ' + self.gmsh_file_init
			os.system(copy_mesh)
			self.gmsh_file = self.gmsh_file_init



	def __setup_quality_measurement(self):
		pass



	def move_mesh(self, transformation):
		r"""Transforms the mesh by perturbation of identity.

		Moves the mesh according to the deformation given by
		$$\text{id} + \mathcal{V}(x),
		$$
		where \(\mathcal{V}\) is the transformation. This
		represents the perturbation of identity.

		Parameters
		----------
		transformation : dolfin.function.function.Function
			The transformation for the mesh, a vector CG1 Function
		"""

		assert transformation.ufl_element().family() == 'Lagrange' and \
			   transformation.ufl_element().degree() == 1, 'Not a valid mesh transformation'

		if not self.__test_a_priori(transformation):
			return False
		else:
			self.old_coordinates = self.mesh.coordinates().copy()
			fenics.ALE.move(self.mesh, transformation)
			self.bbtree.build(self.mesh)

			return self.__test_a_posteriori()



	def revert_transformation(self):
		"""Reverts a mesh transformation.

		This is used when the mesh quality for the resulting deformed mesh
		is not sufficient, or when the solution algorithm terminates due
		to lack of decrease in the Armijo rule, e.g..

		Returns
		-------
		None
		"""

		self.mesh.coordinates()[:, :] = self.old_coordinates
		self.bbtree.build(self.mesh)



	def __setup_decrease_computation(self):
		"""Initializes attributes and solver for the frobenius norm check

		Returns
		-------
		None
		"""

		assert self.angle_change > 0, 'Angle change has to be positive'

		options = [[
				['ksp_type', 'preonly'],
				['pc_type', 'jacobi'],
				['pc_jacobi_type', 'diagonal'],
				['ksp_rtol', 1e-16],
				['ksp_atol', 1e-20],
				['ksp_max_it', 1000]
		]]
		self.ksp_frobenius = PETSc.KSP().create()
		_setup_petsc_options([self.ksp_frobenius], options)

		self.trial_dg0 = fenics.TrialFunction(self.shape_form_handler.DG0)
		self.test_dg0 = fenics.TestFunction(self.shape_form_handler.DG0)

		if not self.angle_change == float('inf'):
			self.search_direction_container = fenics.Function(self.shape_form_handler.deformation_space)

			self.a_frobenius = self.trial_dg0*self.test_dg0*self.dx
			self.L_frobenius = fenics.sqrt(fenics.inner(fenics.grad(self.search_direction_container), fenics.grad(self.search_direction_container)))*self.test_dg0*self.dx



	def compute_decreases(self, search_direction, stepsize):
		"""Estimates the number of Armijo decreases for a certain mesh quality.

		Gives a better estimation of the stepsize. The output is
		the number of Armijo decreases we have to do in order to
		get a transformation that satisfies norm(transformation)_fro <= tol,
		where transformation = stepsize*search_direction and tol is specified in
		the config file under "angle_change". Due to the linearity
		of the norm this has to be done only once, all smaller stepsizes are
		feasible wrt. to this criterion as well

		Parameters
		----------
		search_direction : dolfin.function.function.Function
			The search direction in the optimization routine / descent algorithm
		stepsize : float
			The stepsize in the descent algorithm

		Returns
		-------
		int
			A guess for the number of "Armijo halvings" to get a better stepsize
		"""


		assert self.angle_change > 0, 'Angle change has to be positive'
		if self.angle_change == float('inf'):
			return 0

		else:
			self.search_direction_container.vector()[:] = search_direction.vector()[:]
			A, b = _assemble_petsc_system(self.a_frobenius, self.L_frobenius)
			b = fenics.as_backend_type(fenics.assemble(self.L_frobenius)).vec()
			x, _ = A.getVecs()

			self.ksp_frobenius.setOperators(A)
			self.ksp_frobenius.solve(b, x)
			if self.ksp_frobenius.getConvergedReason() < 0:
				raise Exception('Krylov solver did not converge. Reason: ' + str(self.ksp_frobenius.getConvergedReason()))

			frobenius_norm = np.max(x[:])
			beta_armijo = self.config.getfloat('OptimizationRoutine', 'beta_armijo', fallback=2)

			return np.maximum(np.ceil(np.log(self.angle_change/stepsize/frobenius_norm)/np.log(1/beta_armijo)), 0.0)



	def __setup_a_priori(self):
		"""Sets up the attributes and petsc solver for the a priori quality check

		Returns
		-------
		None
		"""

		if self.volume_change < float('inf'):
			options = [[
				['ksp_type', 'preonly'],
				['pc_type', 'jacobi'],
				['pc_jacobi_type', 'diagonal'],
				['ksp_rtol', 1e-16],
				['ksp_atol', 1e-20],
				['ksp_max_it', 1000]
			]]
			self.ksp_prior = PETSc.KSP().create()
			_setup_petsc_options([self.ksp_prior], options)

			self.transformation_container = fenics.Function(self.shape_form_handler.deformation_space)
			dim = self.mesh.geometric_dimension()
			assert self.volume_change > 1, 'Volume change has to be larger than 1'
			self.a_prior = self.trial_dg0*self.test_dg0*self.dx
			self.L_prior = fenics.det(fenics.Identity(dim) + fenics.grad(self.transformation_container))*self.test_dg0*self.dx



	def __test_a_priori(self, transformation):
		"""Check the quality of the transformation before the actual mesh is moved.

		Checks the quality of the transformation. The criterion is that
		 det(I + D transformation) should neither be too large nor too small
		in order to achieve the best transformations.

		Parameters
		----------
		transformation : dolfin.function.function.Function
			The transformation for the mesh

		Returns
		-------
		bool
			A boolean that indicates whether the desired transformation is feasible
		"""

		if self.volume_change < float('inf'):

			self.transformation_container.vector()[:] = transformation.vector()[:]
			A, b = _assemble_petsc_system(self.a_prior, self.L_prior)
			b = fenics.as_backend_type(fenics.assemble(self.L_prior)).vec()
			x, _ = A.getVecs()

			self.ksp_prior.setOperators(A)
			self.ksp_prior.solve(b, x)
			if self.ksp_prior.getConvergedReason() < 0:
				raise Exception('Krylov solver did not converge. Reason: ' + str(self.ksp_prior.getConvergedReason()))

			min_det = np.min(x[:])
			max_det = np.max(x[:])

			return (min_det >= 1/self.volume_change) and (max_det <= self.volume_change)

		else:
			return True



	def __test_a_posteriori(self):
		"""Check the quality of the transformation after the actual mesh is moved.

		Checks whether the mesh is a valid finite element mesh
		after it has been moved, i.e., if there are no overlapping
		or self intersecting elements.

		Returns
		-------
		bool
			True if the test is successful, False otherwise
		"""


		mesh = self.mesh
		cells = mesh.cells()
		coordinates = mesh.coordinates()
		self_intersections = False
		for i in range(coordinates.shape[0]):
			x = fenics.Point(coordinates[i])
			cells_idx = self.bbtree.compute_entity_collisions(x)
			intersections = len(cells_idx)
			M = cells[cells_idx]
			occurences = M.flatten().tolist().count(i)

			if intersections > occurences:
				self_intersections = True
				break

		if self_intersections:
			self.revert_transformation()
			return False
		else:
			self.compute_mesh_quality()
			return True



	def compute_mesh_quality(self):
		"""This computes the current mesh quality.

		Updates the attribute current_mesh_quality.

		Returns
		-------
		None
		"""

		if self.mesh_quality_type in ['min', 'minimum']:
			if self.mesh_quality_measure == 'skewness':
				self.current_mesh_quality = MeshQuality.min_skewness(self.mesh)
			elif self.mesh_quality_measure == 'maximum_angle':
				self.current_mesh_quality = MeshQuality.min_maximum_angle(self.mesh)
			elif self.mesh_quality_measure == 'radius_ratios':
				self.current_mesh_quality = MeshQuality.min_radius_ratios(self.mesh)
			elif self.mesh_quality_measure == 'condition_number':
				self.current_mesh_quality = MeshQuality.min_condition_number(self.mesh)

		else:
			if self.mesh_quality_measure == 'skewness':
				self.current_mesh_quality = MeshQuality.avg_skewness(self.mesh)
			elif self.mesh_quality_measure == 'maximum_angle':
				self.current_mesh_quality = MeshQuality.avg_maximum_angle(self.mesh)
			elif self.mesh_quality_measure == 'radius_ratios':
				self.current_mesh_quality = MeshQuality.avg_radius_ratios(self.mesh)
			elif self.mesh_quality_measure == 'condition_number':
				self.current_mesh_quality = MeshQuality.avg_condition_number(self.mesh)



	def __generate_remesh_geo(self, input_mesh_file):
		"""Generates a .geo file used for remeshing

		The .geo file is generated via the original .geo file for the
		initial geometry, so that mesh size fields are correctly given
		for the remeshing

		Parameters
		----------
		input_mesh_file : str
			Path to the mesh file used for generating the new .geo file

		Returns
		-------
		None
		"""

		with open(self.remesh_geo_file, 'w') as file:
			temp_name = os.path.split(input_mesh_file)[1]

			file.write('Merge \'' + temp_name + '\';\n')
			file.write('CreateGeometry;\n')
			file.write('\n')

			geo_file = self.temp_dict['geo_file']
			with open(geo_file, 'r') as f:
				for line in f:
					if line[:2] == 'lc':
						file.write(line)
					if line[:5] == 'Field':
						file.write(line)
					if line[:16] == 'Background Field':
						file.write(line)



	def remesh(self):
		"""Remeshes the current geometry with gmsh.

		Performs a remeshing of the geometry, and then restarts
		the optimization problem with the new mesh.

		Returns
		-------
		None
		"""

		if self.do_remesh:
			self.remesh_counter += 1
			self.temp_file = self.remesh_directory + '/mesh_' + format(self.remesh_counter, 'd') + '_pre_remesh' + '.msh'
			write_out_mesh(self.mesh, self.gmsh_file, self.temp_file)
			self.__generate_remesh_geo(self.temp_file)

			# save the output dict (without the last entries since they are "remeshed")
			self.temp_dict['output_dict'] = {}
			self.temp_dict['output_dict']['state_solves'] = self.shape_optimization_problem.state_problem.number_of_solves
			self.temp_dict['output_dict']['adjoint_solves'] = self.shape_optimization_problem.adjoint_problem.number_of_solves
			self.temp_dict['output_dict']['iterations'] = self.shape_optimization_problem.solver.iteration

			self.temp_dict['output_dict']['cost_function_value'] = self.shape_optimization_problem.solver.output_dict['cost_function_value'][:-1]
			self.temp_dict['output_dict']['gradient_norm'] = self.shape_optimization_problem.solver.output_dict['gradient_norm'][:-1]
			self.temp_dict['output_dict']['stepsize'] = self.shape_optimization_problem.solver.output_dict['stepsize'][:-1]
			self.temp_dict['output_dict']['MeshQuality'] = self.shape_optimization_problem.solver.output_dict['MeshQuality'][:-1]

			dim = self.mesh.geometric_dimension()

			self.new_gmsh_file = self.remesh_directory + '/mesh_' + format(self.remesh_counter, 'd') + '.msh'
			gmsh_command = 'gmsh ' + self.remesh_geo_file + ' -' + str(int(dim)) + ' -o ' + self.new_gmsh_file
			if not self.config.getboolean('Mesh', 'show_gmsh_output', fallback=False):
				os.system(gmsh_command + ' >/dev/null 2>&1')
			else:
				os.system(gmsh_command)

			self.temp_dict['remesh_counter'] = self.remesh_counter

			# rename_command = 'mv ' + self.temp_file + ' ' + self.new_gmsh_file
			# os.system(rename_command)

			self.new_xdmf_file = self.remesh_directory + '/mesh_' + format(self.remesh_counter, 'd') + '.xdmf'
			convert_command = 'mesh-convert ' + self.new_gmsh_file + ' ' + self.new_xdmf_file
			os.system(convert_command)

			self.temp_dict['mesh_file'] = self.new_xdmf_file
			self.temp_dict['gmsh_file'] = self.new_gmsh_file

			# test, whether the same geometry is remeshed again
			if self.temp_dict['OptimizationRoutine']['iteration_counter'] == self.shape_optimization_problem.solver.iteration:
				raise Exception('Remeshing the geometry failed.')

			self.temp_dict['OptimizationRoutine']['iteration_counter'] = self.shape_optimization_problem.solver.iteration
			self.temp_dict['OptimizationRoutine']['gradient_norm_initial'] = self.shape_optimization_problem.solver.gradient_norm_initial

			self.temp_dir = self.temp_dict['temp_dir']

			with open(self.temp_dir + '/temp_dict.json', 'w') as file:
				json.dump(self.temp_dict, file)

			if not '_cestrel_remesh_flag' in sys.argv:
				os.execv(sys.executable, [sys.executable] + sys.argv + ['_cestrel_remesh_flag'] + [self.temp_dir])
			else:
				os.execv(sys.executable, [sys.executable] + sys.argv[:-2] + ['_cestrel_remesh_flag'] + [self.temp_dir])





class MeshQuality:
	r"""A class used to compute the quality of a mesh.

	This class implements either a skewness quality measure, one based
	on the maximum angle of the elements, or one based on the radius ratios.
	All quality measures have values in \( [0, 1] \), where 1 corresponds
	to the best / perfect element, and 0 corresponds to degenerate elements.

	Examples
	--------
	This class can be directly used, without any instantiation. E.g., with
	cestrel one can write

		import cestrel

		mesh, _, _, _, _, _ = cestrel.regular_mesh(10)

		min_skew = cestrel.MeshQuality.min_skewness(mesh)
		avg_skew = cestrel.MeshQuality.avg_skewness(mesh)

		min_angle = cestrel.MeshQuality.min_maximum_angle(mesh)
		avg_angle = cestrel.MeshQuality.avg_maximum_angle(mesh)

		min_rad = cestrel.MeshQuality.min_radius_ratios(mesh)
		avg_rad = cestrel.MeshQuality.avg_radius_ratios(mesh)

		min_cond = cestrel.MeshQuality.min_condition_number(mesh)
		avg_cond = cestrel.MeshQuality.avg_condition_number(mesh)

	This works analogously for any mesh used in fenics.

	See Also
	--------
	MeshQuality.min_skewness : Computes the quality measure based on the skewness of the mesh.
	MeshQuality.min_maximum_angle : Computes the quality measure based on the maximum angle of the elements.
	MeshQuality.min_radius_ratios : Computes the quality measure based on the radius ratios.
	MeshQuality.min_condition_number : Computes the quality based on the condition number of the mapping from element to reference element.
	"""

	_cpp_code_mesh_quality = """
			#include <pybind11/pybind11.h>
			#include <pybind11/eigen.h>
			namespace py = pybind11;
			
			#include <dolfin/mesh/Mesh.h>
			#include <dolfin/mesh/Vertex.h>
			#include <dolfin/mesh/MeshFunction.h>
			#include <dolfin/mesh/Cell.h>
			#include <dolfin/mesh/Vertex.h>
			
			using namespace dolfin;
			
			
			void angles_triangle(const Cell& cell, std::vector<double>& angs)
			{
			  const Mesh& mesh = cell.mesh();
			  angs.resize(3);
			  const std::size_t i0 = cell.entities(0)[0];
			  const std::size_t i1 = cell.entities(0)[1];
			  const std::size_t i2 = cell.entities(0)[2];
			  
			  const Point p0 = Vertex(mesh, i0).point();
			  const Point p1 = Vertex(mesh, i1).point();
			  const Point p2 = Vertex(mesh, i2).point();
			  Point e0 = p1 - p0;
			  Point e1 = p2 - p0;
			  Point e2 = p2 - p1;
			  
			  e0 /= e0.norm();
			  e1 /= e1.norm();
			  e2 /= e2.norm();
			
			  angs[0] = acos(e0.dot(e1));
			  angs[1] = acos(e0.dot(e2));
			  angs[2] = acos(e1.dot(e2));
			}
			
			
			
			void dihedral_angles(const Cell& cell, std::vector<double>& angs)
			{
			  const Mesh& mesh = cell.mesh();
			  angs.resize(6);
			  
			  const std::size_t i0 = cell.entities(0)[0];
			  const std::size_t i1 = cell.entities(0)[1];
			  const std::size_t i2 = cell.entities(0)[2];
			  const std::size_t i3 = cell.entities(0)[3];
			  
			  const Point p0 = Vertex(mesh, i0).point();
			  const Point p1 = Vertex(mesh, i1).point();
			  const Point p2 = Vertex(mesh, i2).point();
			  const Point p3 = Vertex(mesh, i3).point();
			  
			  const Point e0 = p1 - p0;
			  const Point e1 = p2 - p0;
			  const Point e2 = p3 - p0;
			  const Point e3 = p2 - p1;
			  const Point e4 = p3 - p1;
			  
			  Point n0 = e0.cross(e1);
			  Point n1 = e0.cross(e2);
			  Point n2 = e1.cross(e2);
			  Point n3 = e3.cross(e4);
			  
			  n0 /= n0.norm();
			  n1 /= n1.norm();
			  n2 /= n2.norm();
			  n3 /= n3.norm();
			  
			  angs[0] = acos(n0.dot(n1));
			  angs[1] = acos(-n0.dot(n2));
			  angs[2] = acos(n1.dot(n2));
			  angs[3] = acos(n0.dot(n3));
			  angs[4] = acos(n1.dot(-n3));
			  angs[5] = acos(n2.dot(n3));
			}
			
			
			
			dolfin::MeshFunction<double>
			skewness(std::shared_ptr<const Mesh> mesh)
			{
			  MeshFunction<double> cf(mesh, mesh->topology().dim(), 0.0);
			  
			  double opt_angle;
			  std::vector<double> angs;
			  std::vector<double> quals;
			  
			  for (CellIterator cell(*mesh); !cell.end(); ++cell)
			  {
				if (cell->dim() == 2)
				{
				  quals.resize(3);
				  angles_triangle(*cell, angs);
				  opt_angle = DOLFIN_PI / 3.0;
				}
				else if (cell->dim() == 3)
				{
				  quals.resize(6);
				  dihedral_angles(*cell, angs);
				  opt_angle = acos(1.0/3.0);
				}
				else
				{
				  dolfin_error("cestrel_quality.cpp", "skewness", "Not a valid dimension for the mesh.");
				}
				
				for (unsigned int i = 0; i < angs.size(); ++i)
				{
				  quals[i] = 1 - std::max((angs[i] - opt_angle) / (DOLFIN_PI - opt_angle), (opt_angle - angs[i]) / opt_angle);
				}
				cf[*cell] = *std::min_element(quals.begin(), quals.end());
			  }
			  return cf;
			}
			
			
			
			dolfin::MeshFunction<double>
			maximum_angle(std::shared_ptr<const Mesh> mesh)
			{
			  MeshFunction<double> cf(mesh, mesh->topology().dim(), 0.0);
			  
			  double opt_angle;
			  std::vector<double> angs;
			  std::vector<double> quals;
			  
			  for (CellIterator cell(*mesh); !cell.end(); ++cell)
			  {
				if (cell->dim() == 2)
				{
				  quals.resize(3);
				  angles_triangle(*cell, angs);
				  opt_angle = DOLFIN_PI / 3.0;
				}
				else if (cell->dim() == 3)
				{
				  quals.resize(6);
				  dihedral_angles(*cell, angs);
				  opt_angle = acos(1.0/3.0);
				}
				else
				{
				  dolfin_error("cestrel_quality.cpp", "maximum_angle", "Not a valid dimension for the mesh.");
				}
				
				for (unsigned int i = 0; i < angs.size(); ++i)
				{
				  quals[i] = 1 - std::max((angs[i] - opt_angle) / (DOLFIN_PI - opt_angle), 0.0);
				}
				cf[*cell] = *std::min_element(quals.begin(), quals.end());
			  }
			  return cf;
			}
			
			PYBIND11_MODULE(SIGNATURE, m)
			{
			  m.def("skewness", &skewness);
			  m.def("maximum_angle", &maximum_angle);
			}
		
		"""
	_quality_object = fenics.compile_cpp_code(_cpp_code_mesh_quality)



	def __init__(self):
		"""Initializes self.

		"""
		pass



	@classmethod
	def min_skewness(cls, mesh):
		r"""Computes the minimal skewness of the mesh.

		This measure the relative distance of a triangle's angles or
		a tetrahedrons dihedral angles to the corresponding optimal
		angle. The optimal angle is defined as the angle an equilateral,
		and thus equiangular, element has. The skewness lies in
		\( [0,1] \), where 1 corresponds to the case of an optimal
		(equilateral) element, and 0 corresponds to a degenerate
		element. The skewness corresponding to some (dihedral) angle
		\( \alpha \) is defined as

		$$ 1 - \max \left( \frac{\alpha - \alpha^*}{\pi - \alpha*} , \frac{\alpha^* - \alpha}{\alpha^* - 0} \right)
		$$

		To compute the (global) quality measure, the minimum of this expression
		over all elements and all of their (dihedral) angles is computed.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh whose quality shall be computed.

		Returns
		-------
		float
			The skewness of the mesh.
		"""

		return np.min(cls._quality_object.skewness(mesh).array())



	@classmethod
	def avg_skewness(cls, mesh):
		r"""Computes the average skewness of the mesh.

		See Also
		--------
		min_skewness : Computes the minimal skewness of the mesh.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		flat
			The average skewness of the mesh.
		"""

		return np.average(cls._quality_object.maximum_angle(mesh).array())



	@classmethod
	def min_maximum_angle(cls, mesh):
		r"""Computes the minimal quality measure based on the largest angle.

		This measures the relative distance of a triangle's angles or a
		tetrahedron's dihedral angles to the corresponding optimal
		angle. The optimal angle is defined as the angle an equilateral
		(and thus equiangular) element has. This is defined as

		$$ 1 - \max\left( \frac{\alpha - \alpha^*}{\pi - \alpha^*} , 0 \right),
		$$

		where \( \alpha \) is the corresponding (dihedral) angle of the element.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		float
			The minimum value of the maximum angle quality measure.
		"""

		return np.min(cls._quality_object.maximum_angle(mesh).array())



	@classmethod
	def avg_maximum_angle(cls, mesh):
		r"""Computes the average quality of the mesh based on the maximum angle.

		See Also
		--------
		min_maximum_angle : Computes the minimal quality measure based on the maximum angle.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		float
			The average quality, based on the maximum angle measure.
		"""

		return np.average(cls._quality_object.maximum_angle(mesh).array())


	@staticmethod
	def min_radius_ratios(mesh):
		r"""Computes the minimal radius ratio of the mesh.

		This measures the ratio of the element's inradius to it's circumradius,
		normalized by the geometric dimension. It is an element of \( [0,1] \),
		where 1 indicates best element quality and 0 is obtained for degenerate
		elements. This is computed via

		$$d \frac{r}{R},
		$$

		where \(d\) is the spatial dimension, \(r\) is the inradius, and \(R\) is
		the circumradius. To compute the (global) quality measure, the minimum
		of this expression over all elements is returned.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose radius ratios shall be computed.

		Returns
		-------
		float
			The minimal radius ratio of the mesh.
		"""

		return np.min(fenics.MeshQuality.radius_ratios(mesh).array())



	@staticmethod
	def avg_radius_ratios(mesh):
		r"""Computes the average radius ratio of the mesh.

		See Also
		--------
		min_radius_ratios : Computes the minimal radius ratio of the mesh.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		float
			The average radius ratio of the mesh.
		"""

		return np.average(fenics.MeshQuality.radius_ratios(mesh).array())



	@staticmethod
	def min_condition_number(mesh):
		r"""Computes minimal mesh quality based on the condition number of the reference mapping.

		This quality criterion uses the condition number (in the Frobenius norm) of the
		(linear) mapping from the elements of the mesh to the reference element. Computes
		the minimum of the condition number over all elements.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		float
			The minimal condition number quality measure.
		"""

		DG0 = fenics.FunctionSpace(mesh, 'DG', 0)
		jac = Jacobian(mesh)
		inv = JacobianInverse(mesh)

		options = [[
				['ksp_type', 'preonly'],
				['pc_type', 'jacobi'],
				['pc_jacobi_type', 'diagonal'],
				['ksp_rtol', 1e-16],
				['ksp_atol', 1e-20],
				['ksp_max_it', 1000]
			]]
		ksp = PETSc.KSP().create()
		_setup_petsc_options([ksp], options)

		dx = fenics.Measure('dx', mesh)
		a = fenics.TrialFunction(DG0)*fenics.TestFunction(DG0)*dx
		L = fenics.sqrt(fenics.inner(jac, jac))*fenics.sqrt(fenics.inner(inv, inv))*fenics.TestFunction(DG0)*dx

		cond = fenics.Function(DG0)

		A, b = _assemble_petsc_system(a, L)
		ksp.setOperators(A)
		ksp.solve(b, cond.vector().vec())

		return np.min(np.sqrt(mesh.geometric_dimension()) / cond.vector()[:])



	@staticmethod
	def avg_condition_number(mesh):
		"""Computes the average mesh quality based on the condition number of the reference mapping.

		See Also
		--------
		min_condition_number : Computes the minimum condition number quality measure.

		Parameters
		----------
		mesh : dolfin.cpp.mesh.Mesh
			The mesh, whose quality shall be computed.

		Returns
		-------
		float
			The average mesh quality based on the condition number.
		"""

		DG0 = fenics.FunctionSpace(mesh, 'DG', 0)
		jac = Jacobian(mesh)
		inv = JacobianInverse(mesh)

		options = [[
				['ksp_type', 'preonly'],
				['pc_type', 'jacobi'],
				['pc_jacobi_type', 'diagonal'],
				['ksp_rtol', 1e-16],
				['ksp_atol', 1e-20],
				['ksp_max_it', 1000]
			]]
		ksp = PETSc.KSP().create()
		_setup_petsc_options([ksp], options)

		dx = fenics.Measure('dx', mesh)
		a = fenics.TrialFunction(DG0)*fenics.TestFunction(DG0)*dx
		L = fenics.sqrt(fenics.inner(jac, jac))*fenics.sqrt(fenics.inner(inv, inv))*fenics.TestFunction(DG0)*dx

		cond = fenics.Function(DG0)

		A, b = _assemble_petsc_system(a, L)
		ksp.setOperators(A)
		ksp.solve(b, cond.vector().vec())

		return np.average(np.sqrt(mesh.geometric_dimension()) / cond.vector()[:])
