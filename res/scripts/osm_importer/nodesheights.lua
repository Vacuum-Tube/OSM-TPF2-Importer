local vec3 = require "vec3"
local tools = require"osm_importer.tools"

local h = {}


function h.setAllNodesHeight(nodes,paths,edges)
	for _,node in pairs(nodes) do
		if node.pos and node.pos[3] then
			print("Node heights already set; skip.")
			return
		end
		break
	end
	local edgedict = {}
	for _,edge in pairs(edges or {}) do
		local k = edge.node0.."--"..edge.node1
		if not edgedict[k] then
			edgedict[k] = edge
			edgedict[edge.node1.."--"..edge.node0] = edge
		end
	end

	paths = paths or {}

	for _,node in pairs(nodes) do
		if node.pos then
			node.pos[3] = tools.safeTerrainZ(node.pos[1], node.pos[2], node.pos[3] or 0)
		end
	end

	local function smoothGroundPath(path)
		if type(path) ~= "table" or #path < 2 then
			return
		end
		local path_z = {}
		local nodes_idx = {}
		for i=1,#path-1 do
			local node0 = path[i]
			local node1 = path[i+1]
			if not nodes[node0] or not nodes[node1] then
				return
			end
			local p0 = nodes[node0].pos
			p0 = vec3.new(p0[1], p0[2], 0)
			local p1 = nodes[node1].pos
			p1 = vec3.new(p1[1], p1[2], 0)
			local edge = edgedict[node0.."--"..node1]
			if not edge then
				return
			end
			if edge.node0~=node0 and edge.node0~=node1 then
				return
			end
			local m0 = (edge.node0==node0) and edge.tangent0 and tools.vec3(edge.tangent0, 0) or (p1-p0)
			local m1 = (edge.node0==node0) and edge.tangent1 and tools.vec3(edge.tangent1, 0) or (p1-p0)
			if not (m0.x and m1.x) then
				return
			end
			local length = vec3.distance(p0, p1)
			local num_steps = math.max(1, math.ceil(length))
			for s=1,num_steps do
				local pi = tools.hermiteSpline(p0, p1, m0, m1, s/num_steps)
				path_z[#path_z+1] = tools.safeTerrainZ(pi.x, pi.y, path_z[#path_z] or 0)
			end
			nodes_idx[node1] = #path_z
		end
		local join = edgedict[path[1].."--"..path[2]]
		if not join or #path_z == 0 then
			return
		end
		local sigma = join.track and 50 or 25
		local window_size = math.ceil(2*sigma)
		local smoothed_z = h.gaussian_smooth(path_z, sigma, window_size)
		for i=2,#path-1 do
			local node = path[i]
			if nodes[node] and nodes_idx[node] then
				nodes[node].pos[3] = smoothed_z[nodes_idx[node]]
			end
		end
	end

	for _,path in pairs(paths.ground or {}) do
		smoothGroundPath(path)
	end
	print("z heights ground paths set ")

	local function liftBridgePath(path)
		if type(path) ~= "table" or #path < 2 or not nodes[path[1]] or not nodes[path[#path]] then
			return
		end
		local p_start = tools.Vec2f(nodes[path[1]].pos)
		local p_end = tools.Vec2f(nodes[path[#path]].pos)
		local z_start = nodes[path[1]].pos[3] or 0
		local z_end = nodes[path[#path]].pos[3] or 0
		local span = tools.VecDist(p_start, p_end)
		if not span or span == 0 then
			return
		end
		for i=2,#path-1 do
			local node = path[i]
			if nodes[node] then
				local p_i = tools.Vec2f(nodes[node].pos)
				nodes[node].pos[3] = z_start + (z_end-z_start)*tools.VecDist(p_start,p_i)/span
			end
		end
	end

	for _,path in pairs(paths.bridge or {}) do
		liftBridgePath(path)
	end
	print("z heights bridge paths set ")

	local function setPathTangents(path)
		if type(path) ~= "table" or #path < 2 then
			return
		end
		local tangents = {}
		for i=2,#path-1 do
			if not (nodes[path[i-1]] and nodes[path[i]] and nodes[path[i+1]]) then
				return
			end
			local p0 = tools.vec3(nodes[path[i-1]].pos)
			local p1 = tools.vec3(nodes[path[i]].pos)
			local p2 = tools.vec3(nodes[path[i+1]].pos)
			local d01 = vec3.distance(p1,p0)
			local d12 = vec3.distance(p2,p1)
			if d01 == 0 or d12 == 0 then
				return
			end
			local tangZ01 = (p1.z-p0.z)/d01
			local tangZ12 = (p2.z-p1.z)/d12
			local tangZ = 0
			if tangZ12/tangZ01>0 then
				if math.abs(tangZ01)>math.abs(tangZ12) then
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
			if not (nodes[node0] and nodes[node1]) then
				return
			end
			local p0 = tools.vec3(nodes[node0].pos)
			local p1 = tools.vec3(nodes[node1].pos)
			local length = vec3.distance(p0,p1)
			local edge = edgedict[node0.."--"..node1]
			if not edge or edge.node0~=node0 or edge.node1~=node1 then
				return
			end
			if i>1 then
				if not edge.tangent0 then
					edge.tangent0 = {}
				end
				edge.tangent0[3] = (tangents[i] or 0)*length
			end
			if i+1<#path then
				if not edge.tangent1 then
					edge.tangent1 = {}
				end
				edge.tangent1[3] = (tangents[i+1] or 0)*length
			end
		end
	end

	for _,pathss in pairs{paths.track or {}, paths.street or {}} do
		for _,path in pairs(pathss) do
			setPathTangents(path)
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