Merge 'mesh_809b9469f5624c82ab976d1805dc59a5.msh';
CreateGeometry;

lc = 3.5e-2;
Field[1] = Distance;
Field[1].NNodesByEdge = 1000;
Field[1].NodesList = {2};
Field[2] = Threshold;
Field[2].IField = 1;
Field[2].DistMin = 1e-1;
Field[2].DistMax = 5e-1;
Field[2].LcMin = lc / 5;
Field[2].LcMax = lc;
Background Field = 2;
