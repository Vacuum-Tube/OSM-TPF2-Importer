local vec3 = require "vec3"
local tools = require"osm_importer.tools"

local h = {}


function h.setAllNodesHeight(nodes,paths,edges)
	local edgedict = {}  -- encode here to find edge via nodes
	for _,edge in pairs(edges) do
		assert(not edgedict[edge.node0.."--"..edge.node1], "assume no duplicate edges "..toString(edge))
		edgedict[edge.node0.."--"..edge.node1] = edge
		edgedict[edge.node1.."--"..edge.node0] = edge
	end
	
	for id,node in pairs(nodes) do  -- fix all node heights before anything is built
		assert(not node.pos[3], "Node pos[3] already set "..id..toString(node))
		node.pos[3] = tools.getTerrainZ(node.pos[1], node.pos[2])
	end
	
	for _,path in pairs(paths.ground) do  -- paths between crossings and bridge ends
		local path_z = {}
		local nodes_idx = {}
		for i=1,#path-1 do
			local node0 = path[i]
			local node1 = path[i+1]
			local p0 = nodes[node0].pos
			p0 = vec3.new(p0[1], p0[2], 0)  -- vec2 has no meta methods
			local p1 = nodes[node1].pos
			p1 = vec3.new(p1[1], p1[2], 0)
			local edge = assert(edgedict[node0.."--"..node1], "No edge "..node0.."-"..node1)
			if edge.node0~=node0 then  -- edge reverse to path
				assert(edge.node0==node1)
			end
			local m0 = (edge.node0==node0) and edge.tangent0 and tools.vec3(edge.tangent0, 0) or (p1-p0)
			local m1 = (edge.node0==node0) and edge.tangent1 and tools.vec3(edge.tangent1, 0) or (p1-p0)
			assert(m0.x and m1.x, "error with vectors "..toString(edge))
			-- assert(vec3.angleUnit(vec3.normalize(p1-p0), vec3.normalize(m0))*180/math.pi<80, toString(edge))
			-- assert(vec3.angleUnit(vec3.normalize(p1-p0), vec3.normalize(m1))*180/math.pi<80, toString(edge))
			local length = vec3.distance(p0, p1)
			local num_steps = math.ceil(length)  -- approximately equi-distant (1m)
			for i=1,num_steps do  -- collect terrain heigtht along the hermite curve between nodes
				local pi = tools.hermiteSpline(p0, p1, m0, m1, i/num_steps)
				table.insert(path_z, tools.getTerrainZ(pi.x, pi.y))
				-- table.insert(z_spline, {
					-- p = pi,
					-- x = (#z_spline==0) and 0 or (z_spline[#z_spline].x + vec3.distance(pi, z_spline[#z_spline].p)),
				-- })
			end
			nodes_idx[node1] = #path_z
		end
		
		-- apply Gaussian Filter
		-- local max_slope = 0.04/2  -- maximal derivative of step response: 1/(sqrt(2pi)*sigma) * step_size!
		local sigma = edgedict[path[1].."--"..path[2]].track and 50 or 25  --1/(math.sqrt(2*math.pi)*max_slope)  -- [meters]
		local window_size = math.ceil(2*sigma)  -- make not too big in case of unintended terrain, e.g. overpass
		local smoothed_z = h.gaussian_smooth(path_z, sigma, window_size)
		-- path ends z can also change
		
		for i=2,#path-1 do  -- set node heights
			local node = path[i]
			nodes[node].pos[3] = smoothed_z[nodes_idx[node]]
		end
		
		-- for _,node in pairs{path[1],path[#path]} do  -- fix node heights of path endpoints
			-- nodes[node].pos[3] = tools.getTerrainZ(nodes[node].pos[1], nodes[node].pos[2])
		-- end
	end
	print("z heights ground paths set ")
	
	for _,path in pairs(paths.bridge) do  -- linear interpolation to place intermediate bridge nodes in the air
		local p_start = tools.Vec2f(nodes[path[1]].pos)
		local p_end = tools.Vec2f(nodes[path[#path]].pos)
		local z_start = assert(nodes[path[1]].pos[3], "Node no z value: "..path[1])
		local z_end = assert(nodes[path[#path]].pos[3], "Node no z value: "..path[#path])
		for i,node in pairs(path) do
			local p_i = tools.Vec2f(nodes[path[i]].pos)
			if i>1 and i<#path then
				nodes[node].pos[3] = z_start + (z_end-z_start)*tools.VecDist(p_start,p_i)/tools.VecDist(p_start,p_end)
			end
		end
	end
	print("z heights bridge paths set ")
	
	
	  -- set z tangents 
	for _,pathss in pairs{paths.track, paths.street} do
	for _,path in pairs(pathss) do
		local tangents = {}
		for i=2,#path-1 do
			local p0 = tools.vec3(nodes[path[i-1]].pos)  -- now with z
			local p1 = tools.vec3(nodes[path[i]].pos)
			local p2 = tools.vec3(nodes[path[i+1]].pos)
			local tangZ01 = (p1.z-p0.z)/vec3.distance(p1,p0)
			local tangZ12 = (p2.z-p1.z)/vec3.distance(p2,p1)
			local tangZ = 0
			if tangZ12/tangZ01>0 then  -- keep 0 if rise and fall
				if math.abs(tangZ01)>math.abs(tangZ12) then  -- keep slopes low at the starts/ends
					tangZ = tangZ12
				else
					tangZ = tangZ01
				end
			end
			tangents[i] = tangZ
		end
		
		for i=1,#path-1 do
			local node0 = path[i]
			local node1 = path[i+1]
			local p0 = tools.vec3(nodes[node0].pos)
			local p1 = tools.vec3(nodes[node1].pos)
			local length = vec3.distance(p0,p1)
			local edge = assert(edgedict[node0.."--"..node1])
			assert(edge.node0==node0, node0)
			assert(edge.node1==node1, node1)
			if i>1 then
				if not edge.tangent0 then
					edge.tangent0 = {}
				end
				edge.tangent0[3] = tangents[i]*length
				if tangents[i]/(p1.z-p0.z)<0 then
					print("WARNING: at ".. node0 .."different sign tangZ"..toString(tangents[i]).." - diff".. toString(p1.z-p0.z))
				end
			end
			if i+1<#path then
				if not edge.tangent1 then
					edge.tangent1 = {}
				end
				edge.tangent1[3] = tangents[i+1]*length
			end
		end
	end
	end	
	print("z tangents set")
end


function h.gaussian_smooth(values, sigma, window_size)
    local weights = h.gaussian_weights(sigma, window_size)
    local smoothed_values = {}
    local n = #values
    for i = 1, n do
		local sm_value = 0
		for j = -window_size, window_size do
			local index = i + j
			if index >= 1 and index <= n then
				sm_value = sm_value + values[index] * weights[j]
			elseif index<1 then
				sm_value = sm_value + values[1] * weights[j]  -- pretend constant continuation behind endpoint
			elseif index>n then
				sm_value = sm_value + values[n] * weights[j]
			end
		end
		smoothed_values[i] = sm_value
    end
    return smoothed_values
end

function h.gaussian_weights(sigma, window_size)
    local weights = {}
    local sum = 0
    for i = -window_size, window_size do
        local weight = math.exp(-0.5 * (i / sigma) ^ 2)
        weights[i] = weight
        sum = sum + weight
    end
    for i,weight in pairs(weights) do
        weights[i] = weights[i] / sum
    end
    return weights
end

return h