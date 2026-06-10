"""Publishes 8 seeded readings with declining moisture to test the chart trend."""
import asyncio, json, time, uuid
import aiomqtt

BROKER   = '140.245.7.35'
LOCATION = 'chandigarh'
DEVICE   = 'TESTDEV001'

# 8 hourly readings — moisture 62% → 34% (declining trend, clearly visible on chart)
readings = [
    {'m': 620, 'tp': 265, 'h': 710},
    {'m': 588, 'tp': 271, 'h': 698},
    {'m': 551, 'tp': 280, 'h': 685},
    {'m': 510, 'tp': 287, 'h': 672},
    {'m': 473, 'tp': 291, 'h': 661},
    {'m': 435, 'tp': 295, 'h': 648},
    {'m': 389, 'tp': 299, 'h': 630},
    {'m': 342, 'tp': 303, 'h': 612},
]

async def pub():
    base_ts = int(time.time()) - (len(readings) * 3600)
    async with aiomqtt.Client(BROKER) as client:
        for i, v in enumerate(readings):
            mid = 'chart-seed-' + uuid.uuid4().hex[:6]
            payload = {
                't': DEVICE,
                'ts': base_ts + (i * 3600),
                's': 1,
                'v': v,
                'b': 375,
                'r': -68,
                'a': 1,
                'mid': mid
            }
            await client.publish(LOCATION + '/' + DEVICE + '/telemetry',
                                 json.dumps(payload), qos=1)
            moisture_val = v['m'] / 10
            print('Published reading ' + str(i+1) + '/' + str(len(readings))
                  + ': moisture=' + str(moisture_val) + '%')
            await asyncio.sleep(0.3)
    print('Done — chart should now show declining moisture trend.')

asyncio.run(pub())
