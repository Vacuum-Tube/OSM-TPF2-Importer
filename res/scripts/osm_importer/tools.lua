require "serialize"
local vec3 = require "vec3"
local streetutil = require "streetutil"


local t = {}


function t.list2dict(list)
	local dict = {}
	for _,item in pairs(list) do
		dict[item] = true
	end
	return dict
end


function t.vec3(v, z_default)
	return vec3.new(v[1], v[2], v[3] or z_default)
end

function t.Vec2f(v)
	return api.type.Vec2f.new(v[1], v[2])
end

function t.Vec3f(v)
	return api.type.Vec3f.new(v[1], v[2], v[3])
end

function t.Vec3Mul(v,f)  -- warum habt ihr keine meta method.......
	return api.type.Vec3f.new(v.x*f, v.y*f, v.z*f)
end

function t.VecNorm(v1,v2)
	local d
	if v2 then
		d = v2-v1
	else
		d = v1
	end
	return d*d
end

function t.VecDist(v1,v2)
	return math.sqrt(t.VecNorm(v1,v2))
end

function t.VecNormalize(v)
	return t.Vec3Mul(v, 1/t.VecDist(v))
end

function t.VecAngleCos(v1,v2)
	return v1*v2/t.VecDist(v1)/t.VecDist(v2)
end

function t.hermiteLength(p0, p1, t0, t1)
	local dist = t.VecDist(p1, p0)
	local angle = vec3.angleUnit(t.VecNormalize(t0), t.VecNormalize(t1))
	return streetutil.calcScale(dist, angle)
end

function t.hermiteSpline(p0, p1, m0, m1, t)
    local t2 = t * t
    local t3 = t2 * t
    local h00 = 2 * t3 - 3 * t2 + 1
    local h01 = t3 - 2 * t2 + t
    local h10 = -2 * t3 + 3 * t2
    local h11 = t3 - t2
    return h00 * p0 + h01 * m0 + h10 * p1 + h11 * m1
end


function t.getTerrainZ(x,y)
	return api.engine.terrain.getHeightAt(api.type.Vec2f.new(x, y))  --getBaseHeightAt
end

function t.isValidCoordinate(x,y)
	return api.engine.terrain.isValidCoordinate(api.type.Vec2f.new(x, y))
end

function t.isOverWater(x,y)
	local terrain = api.engine.getComponent(api.engine.util.getWorld(), api.type.ComponentType.TERRAIN)
	return game.interface.getHeight({x, y}) > terrain.waterLevel
end

function t.getNearestNode(pos,bnodelist,maxdist)
	local c = t.Vec2f(pos)
	local min = (maxdist or math.huge)^2
	local nnode
	for i,nodeid in pairs(bnodelist) do
		local basenode = api.engine.getComponent(nodeid,api.type.ComponentType.BASE_NODE)
		local p = api.type.Vec2f.new(basenode.position.x, basenode.position.y )
		local norm = t.VecNorm(c,p)
		if norm<min then
			min = norm
			nnode = nodeid
		end
	end
	return nnode
end


return t