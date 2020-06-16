lc = 2.5e-2;
radius = 0.33;

Point(1) = {0.0, 0.0, 0.0, lc};
Point(2) = {1.0, 0.0, 0.0, lc};
Point(3) = {1.0, 1.0, 0.0, lc};
Point(4) = {0.0, 1.0, 0.0, lc};

Point(5) = {0.5, 0.5, 0, lc};
Point(6) = {0.5 + radius, 0.5, 0, lc};
Point(7) = {0.5, 0.5 + radius, 0, lc};
Point(8) = {0.5 - radius, 0.5, 0, lc};
Point(9) = {0.5, 0.5 - radius, 0, lc};

Line(1) = {1,2};
Line(2) = {2,3};
Line(3) = {3,4};
Line(4) = {4,1};

Circle(5) = {6, 5, 7};
Circle(6) = {7, 5, 8};
Circle(7) = {8, 5, 9};
Circle(8) = {9, 5, 6};


Line Loop(1) = {1,2,3,4};
Line Loop(2) = {5,6,7,8};

Plane Surface(1) = {1,2};
Plane Surface(2) = {2};

Physical Surface(1) = {1};
Physical Surface(2) = {2};

Physical Line(1) = {1};
Physical Line(2) = {2,3,4};
Physical Line(3) = {5,6,7,8};
