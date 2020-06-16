lc = 5e-2;

Point(1) = {0, 0, 0, lc};
Point(2) = {1, 0, 0, lc};
Point(3) = {0, 1, 0, lc};
Point(4) = {-1, 0, 0, lc};
Point(5) = {0, -1, 0, lc};

Circle(1) = {2, 1, 3};
Circle(2) = {3, 1, 4};
Circle(3) = {4, 1, 5};
Circle(4) = {5, 1, 2};

Line Loop(1) = {1,2,3,4};

Plane Surface(1) = {1};

Physical Surface(1) = {1};

Physical Line(1) = {1,2,3,4};
