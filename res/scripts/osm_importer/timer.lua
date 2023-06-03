local t = {}

function t.timestamp(ts)
	return {
		clock = os.clock(),
		date = os.date("%Y-%m-%d  %H:%M:%S", ts and (os.time()-os.clock()+ts) ),
	}
end


local st = 0
local rnd = 0

function t.start()
	local now = os.clock()
	rnd = now
	st = now
	return now
end

function t.get()
	return os.clock() - st
end

function t.round()
	local now = os.clock()
	local ret = now - rnd
	rnd = now
	return ret
end

function t.stop()
	local ret = t.get()
	t.reset()
	return ret
end

function t.reset()
	st = 0
	rnd = 0
end

function t.timefunc(f,n,...)
	n = n or 1
	t.start()
	for i=1,n do
		f(...)
	end
	local time = t.stop()
	print(string.format("Total Time for %dx: %.3f s %s", n, time,
		n~=1 and string.format("  Average: %.3f ms", time*1000/n) or ""
	))
end

return t