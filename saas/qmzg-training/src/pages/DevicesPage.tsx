import { Button, Card, Form, Input, Modal, Tag, message } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { bindDevice, getDevices, unbindDevice } from '../api/services';
import { Device } from '../api/types';
import AsyncState from '../components/AsyncState';
import { formatDate, maskDeviceId } from '../utils/format';

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [binding, setBinding] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setDevices(await getDevices()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '无法加载设备'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const bind = async ({ deviceId }: { deviceId: string }) => {
    setBinding(true);
    try {
      await bindDevice(deviceId.trim());
      message.success('设备绑定成功');
      form.resetFields();
      await load();
    } catch (reason) { message.error(reason instanceof Error ? reason.message : '绑定失败'); }
    finally { setBinding(false); }
  };

  const confirmUnbind = (device: Device) => {
    Modal.confirm({
      title: '确认解绑真实设备？',
      content: `解绑 ${maskDeviceId(device.id)} 后，当前账号将无法查看该设备的训练历史。`,
      okText: '确认解绑', cancelText: '保留绑定', okButtonProps: { danger: true },
      onOk: async () => { await unbindDevice(device.id); message.success('设备已解绑'); await load(); },
    });
  };

  return (
    <div className="page">
      <div className="page-heading"><div><span className="eyebrow">CONNECTED HARDWARE</span><h1>我的设备</h1><p>管理与训练账号关联的真实 TuyaLink 外骨骼。</p></div></div>
      <AsyncState loading={loading} error={error} onRetry={load}>
        <div className="device-grid">
          {devices.map(device => (
            <Card className="panel-card device-card" bordered={false} key={device.id}>
              <div className="device-card-top"><div className="exo-badge">EXO<small>L610</small></div><Tag color="green">已绑定</Tag></div>
              <h2>{device.display_name || '擎梦智骨外骨骼'}</h2>
              <dl><div><dt>设备标识</dt><dd>{maskDeviceId(device.id)}</dd></div><div><dt>通信链路</dt><dd>4G · TuyaLink</dd></div><div><dt>绑定时间</dt><dd>{formatDate(device.created_at)}</dd></div></dl>
              <div className="device-health"><span className="binding-mark" /> 已绑定到训练账户</div>
              <Button danger type="text" onClick={() => confirmUnbind(device)}>解绑设备</Button>
            </Card>
          ))}
          {!devices.length && <Card className="panel-card device-card empty-device" bordered={false}><div className="exo-badge">EXO<small>READY</small></div><h2>等待设备绑定</h2><p>输入当前真实 Tuya DeviceID，将训练数据归属到本账号。</p></Card>}
        </div>
        <Card className="panel-card bind-card" bordered={false}>
          <div><span className="eyebrow">BIND DEVICE</span><h2>绑定外骨骼</h2><p>DeviceSecret 不会进入浏览器；这里只提交公开的 DeviceID 业务标识。</p></div>
          <Form form={form} layout="inline" onFinish={bind}>
            <Form.Item name="deviceId" rules={[{ required: true, message: '请输入 DeviceID' }, { max: 128 }]}>
              <Input size="large" placeholder="输入 Tuya DeviceID" aria-label="DeviceID" />
            </Form.Item>
            <Button size="large" type="primary" htmlType="submit" loading={binding}>绑定设备</Button>
          </Form>
        </Card>
      </AsyncState>
    </div>
  );
}
