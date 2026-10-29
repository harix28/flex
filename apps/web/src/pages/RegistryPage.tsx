import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { registryApi } from '../services/api';
import { Machine, Sensor, Installation } from '../services/types';
import { ErrorState } from '../components/common/ErrorState';
import { Modal } from '../components/common/Modal';
import {
  Layers,
  Cpu,
  Radio,
  Plus,
  RefreshCw,
  Archive,
  AlertCircle,
} from 'lucide-react';

export const RegistryPage: React.FC = () => {
  const { activeTenant } = useAuth();

  const [activeTab, setActiveTab] = useState<'machines' | 'sensors' | 'installations'>('machines');
  const [machines, setMachines] = useState<Machine[]>([]);
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [selectedMachineId, setSelectedMachineId] = useState<string>('');
  const [installations, setInstallations] = useState<Installation[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Modals
  const [isRegisterMachineOpen, setIsRegisterMachineOpen] = useState(false);
  const [isRegisterSensorOpen, setIsRegisterSensorOpen] = useState(false);
  const [isInstallOpen, setIsInstallOpen] = useState(false);

  // Machine Form
  const [assetCode, setAssetCode] = useState('');
  const [machineName, setMachineName] = useState('');
  const [machineType, setMachineType] = useState('cmapss_engine');
  const [dataSource, setDataSource] = useState<'nasa_replay' | 'physical_device'>('nasa_replay');
  const [subset, setSubset] = useState('FD001');
  const [engineId, setEngineId] = useState<number>(1);
  const [site, setSite] = useState('');
  const [location, setLocation] = useState('');

  // Sensor Form
  const [sensorCode, setSensorCode] = useState('');
  const [sensorName, setSensorName] = useState('');
  const [sensorKind, setSensorKind] = useState('cmapss_channel');
  const [channelId, setChannelId] = useState('sensor_01');

  // Install Form
  const [installSensorId, setInstallSensorId] = useState('');
  const [installChannel, setInstallChannel] = useState('sensor_01');
  const [installNote, setInstallNote] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchRegistryData = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const machRes = await registryApi.listMachines(activeTenant.id, { limit: 100 });
      setMachines(machRes.items);
      if (machRes.items.length > 0 && !selectedMachineId) {
        setSelectedMachineId(machRes.items[0].id);
      }

      const sensRes = await registryApi.listSensors(activeTenant.id, { limit: 100 });
      setSensors(sensRes.items);
      if (sensRes.items.length > 0 && !installSensorId) {
        setInstallSensorId(sensRes.items[0].id);
      }
    } catch (err: any) {
      setError({ message: err.message || 'Failed to load registry data', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant, selectedMachineId, installSensorId]);

  // Load installations when selected machine changes
  useEffect(() => {
    if (!activeTenant || !selectedMachineId) return;
    registryApi.getInstallations(activeTenant.id, selectedMachineId).then((res) => {
      setInstallations(res.items);
    }).catch(() => {
      setInstallations([]);
    });
  }, [activeTenant, selectedMachineId]);

  useEffect(() => {
    fetchRegistryData();
  }, [fetchRegistryData]);

  // Machine Creation Submit
  const handleCreateMachine = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant) return;
    setFormError(null);
    setIsSubmitting(true);

    try {
      const payload: any = {
        asset_code: assetCode.trim(),
        name: machineName.trim(),
        machine_type: machineType.trim(),
        data_source: dataSource,
      };

      if (dataSource === 'nasa_replay') {
        payload.source_binding = {
          dataset: 'C-MAPSS',
          subset,
          engine_id: engineId,
          split: 'test',
        };
      } else {
        if (site.trim()) payload.site = site.trim();
        if (location.trim()) payload.location = location.trim();
      }

      await registryApi.createMachine(activeTenant.id, payload);
      setIsRegisterMachineOpen(false);
      setAssetCode('');
      setMachineName('');
      fetchRegistryData();
    } catch (err: any) {
      setFormError(err.message || 'Failed to register machine');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Sensor Creation Submit
  const handleCreateSensor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant) return;
    setFormError(null);
    setIsSubmitting(true);

    try {
      const payload: any = {
        sensor_code: sensorCode.trim(),
        name: sensorName.trim(),
        kind: sensorKind.trim(),
        data_source: dataSource,
      };

      if (dataSource === 'nasa_replay') {
        payload.channel_id = channelId;
      }

      await registryApi.createSensor(activeTenant.id, payload);
      setIsRegisterSensorOpen(false);
      setSensorCode('');
      setSensorName('');
      fetchRegistryData();
    } catch (err: any) {
      setFormError(err.message || 'Failed to register sensor');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Installation Submit
  const handleInstallSensor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant || !selectedMachineId || !installSensorId) return;
    setFormError(null);
    setIsSubmitting(true);

    try {
      await registryApi.installSensor(activeTenant.id, selectedMachineId, {
        sensor_id: installSensorId,
        channel: installChannel,
        installed_at: new Date().toISOString(),
        note: installNote.trim() || undefined,
      });
      setIsInstallOpen(false);
      setInstallNote('');
      const res = await registryApi.getInstallations(activeTenant.id, selectedMachineId);
      setInstallations(res.items);
    } catch (err: any) {
      setFormError(err.message || 'Failed to map sensor channel');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Archive Machine
  const handleArchiveMachine = async (id: string) => {
    if (!activeTenant || !window.confirm('Are you sure you want to archive this machine? Archived machines preserve history but cannot ingest new data.')) {
      return;
    }
    try {
      await registryApi.archiveMachine(activeTenant.id, id);
      fetchRegistryData();
    } catch (err: any) {
      alert(err.message || 'Failed to archive machine');
    }
  };

  // Close Installation
  const handleRemoveInstallation = async (instId: string) => {
    if (!activeTenant || !window.confirm('Close this sensor channel mapping?')) return;
    try {
      await registryApi.removeInstallation(activeTenant.id, instId, {
        removed_at: new Date().toISOString(),
      });
      const res = await registryApi.getInstallations(activeTenant.id, selectedMachineId);
      setInstallations(res.items);
    } catch (err: any) {
      alert(err.message || 'Failed to close channel mapping');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Registry Management</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Asset configurations, logical C-MAPSS channels, and verified physical hardware records.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchRegistryData}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
        <button
          type="button"
          className={`btn ${activeTab === 'machines' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('machines')}
          style={{ fontSize: '0.8125rem' }}
        >
          <Cpu size={15} />
          <span>Machines ({machines.length})</span>
        </button>

        <button
          type="button"
          className={`btn ${activeTab === 'sensors' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('sensors')}
          style={{ fontSize: '0.8125rem' }}
        >
          <Radio size={15} />
          <span>Sensors ({sensors.length})</span>
        </button>

        <button
          type="button"
          className={`btn ${activeTab === 'installations' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('installations')}
          style={{ fontSize: '0.8125rem' }}
        >
          <Layers size={15} />
          <span>Channel Installations</span>
        </button>
      </div>

      {error && <ErrorState message={error.message} requestId={error.requestId} onRetry={fetchRegistryData} />}

      {/* Tab 1: Machines */}
      {activeTab === 'machines' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setFormError(null);
                setIsRegisterMachineOpen(true);
              }}
            >
              <Plus size={16} />
              <span>Register New Machine</span>
            </button>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Asset Code</th>
                  <th>Name</th>
                  <th>Source Provenance</th>
                  <th>Lifecycle</th>
                  <th>Created At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {machines.map((m) => (
                  <tr key={m.id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{m.asset_code}</td>
                    <td>{m.name}</td>
                    <td>
                      {m.data_source === 'nasa_replay' && m.source_binding ? (
                        <span className="mono" style={{ fontSize: '0.75rem' }}>
                          C-MAPSS {m.source_binding.subset} Engine {m.source_binding.engine_id} ({m.source_binding.split})
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Physical Device</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${m.lifecycle_status === 'active' ? 'badge-low' : 'badge-unknown'}`}>
                        {m.lifecycle_status}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>
                      {new Date(m.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {m.lifecycle_status === 'active' && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => handleArchiveMachine(m.id)}
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', color: 'var(--urgent-text)' }}
                          title="Archive machine (preserves historical telemetry)"
                        >
                          <Archive size={12} />
                          <span>Archive</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Sensors */}
      {activeTab === 'sensors' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setFormError(null);
                setIsRegisterSensorOpen(true);
              }}
            >
              <Plus size={16} />
              <span>Register New Sensor</span>
            </button>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Sensor Code</th>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Source</th>
                  <th>Channel ID</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sensors.map((s) => (
                  <tr key={s.id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{s.sensor_code}</td>
                    <td>{s.name}</td>
                    <td>{s.kind}</td>
                    <td>
                      <span className="badge badge-unknown" style={{ fontSize: '0.7rem' }}>
                        {s.data_source === 'nasa_replay' ? 'NASA Replay' : 'Physical'}
                      </span>
                    </td>
                    <td className="mono">{s.channel_id || '—'}</td>
                    <td>
                      <span className={`badge ${s.status === 'active' ? 'badge-low' : 'badge-unknown'}`}>
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Installations */}
      {activeTab === 'installations' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Target Machine:</span>
              <select
                className="form-control"
                value={selectedMachineId}
                onChange={(e) => setSelectedMachineId(e.target.value)}
                style={{ fontSize: '0.8125rem', padding: '0.35rem 0.65rem' }}
              >
                {machines.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.asset_code} — {m.name}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setFormError(null);
                setIsInstallOpen(true);
              }}
              disabled={!selectedMachineId}
            >
              <Plus size={16} />
              <span>Map Channel Slot</span>
            </button>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Channel Slot</th>
                  <th>Sensor Code</th>
                  <th>Installed At</th>
                  <th>Valid Period</th>
                  <th>Note</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {installations.map((inst) => (
                  <tr key={inst.id}>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--primary)' }}>
                      {inst.channel}
                    </td>
                    <td className="mono">{inst.sensor?.sensor_code || inst.sensor_id}</td>
                    <td className="mono" style={{ fontSize: '0.75rem' }}>
                      {new Date(inst.installed_at).toLocaleString()}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {inst.removed_at ? `Closed ${new Date(inst.removed_at).toLocaleString()}` : 'Active'}
                    </td>
                    <td style={{ fontSize: '0.8125rem' }}>{inst.note || '—'}</td>
                    <td>
                      {!inst.removed_at && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => handleRemoveInstallation(inst.id)}
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                        >
                          Close Mapping
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Register Machine */}
      {isRegisterMachineOpen && (
        <Modal
          isOpen={isRegisterMachineOpen}
          onClose={() => setIsRegisterMachineOpen(false)}
          title="Register New Machine"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsRegisterMachineOpen(false)}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="register-machine-form"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Registering...' : 'Register Machine'}
              </button>
            </>
          }
        >
          <form id="register-machine-form" onSubmit={handleCreateMachine} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
            {formError && (
              <div className="alert alert-danger" style={{ margin: 0 }}>
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="reg-asset-code">
                Asset Code * (Unique stable identifier)
              </label>
              <input
                id="reg-asset-code"
                type="text"
                className="form-control mono"
                value={assetCode}
                onChange={(e) => setAssetCode(e.target.value)}
                placeholder="e.g., NASA-FD001-TEST-1"
                required
                maxLength={64}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-machine-name">
                Display Name *
              </label>
              <input
                id="reg-machine-name"
                type="text"
                className="form-control"
                value={machineName}
                onChange={(e) => setMachineName(e.target.value)}
                placeholder="e.g., SIMULATED FD001 test engine 1"
                required
                maxLength={120}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-machine-type">
                Machine Type *
              </label>
              <input
                id="reg-machine-type"
                type="text"
                className="form-control"
                value={machineType}
                onChange={(e) => setMachineType(e.target.value)}
                placeholder="e.g., cmapss_engine or industrial_gas_turbine"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-data-source">
                Data Source *
              </label>
              <select
                id="reg-data-source"
                className="form-control"
                value={dataSource}
                onChange={(e) => setDataSource(e.target.value as any)}
              >
                <option value="nasa_replay">NASA C-MAPSS Replay</option>
                <option value="physical_device">Physical Device (Connectivity Unverified)</option>
              </select>
            </div>

            {dataSource === 'nasa_replay' && (
              <div
                style={{
                  padding: '0.75rem',
                  backgroundColor: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                }}
              >
                <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>C-MAPSS Source Binding</div>
                <div className="grid-cols-2">
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Subset</label>
                    <select
                      className="form-control"
                      value={subset}
                      onChange={(e) => setSubset(e.target.value)}
                    >
                      <option value="FD001">FD001 (Model Supported)</option>
                      <option value="FD002">FD002 (Unsupported Model)</option>
                      <option value="FD003">FD003 (Unsupported Model)</option>
                      <option value="FD004">FD004 (Unsupported Model)</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Engine ID (Test Partition)</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      className="form-control mono"
                      value={engineId}
                      onChange={(e) => setEngineId(parseInt(e.target.value, 10))}
                      required
                    />
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Phase 4/5 strictly pins to the official <code>test</code> partition to prevent silent train/test conflation.
                </div>
              </div>
            )}

            {dataSource === 'physical_device' && (
              <div className="grid-cols-2">
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Site</label>
                  <input
                    type="text"
                    className="form-control"
                    value={site}
                    onChange={(e) => setSite(e.target.value)}
                    placeholder="e.g., Denver Hangar"
                  />
                </div>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label">Location / Bay</label>
                  <input
                    type="text"
                    className="form-control"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g., Bay 3"
                  />
                </div>
              </div>
            )}
          </form>
        </Modal>
      )}

      {/* Modal: Register Sensor */}
      {isRegisterSensorOpen && (
        <Modal
          isOpen={isRegisterSensorOpen}
          onClose={() => setIsRegisterSensorOpen(false)}
          title="Register New Sensor"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsRegisterSensorOpen(false)}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="register-sensor-form"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Registering...' : 'Register Sensor'}
              </button>
            </>
          }
        >
          <form id="register-sensor-form" onSubmit={handleCreateSensor} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
            {formError && (
              <div className="alert alert-danger" style={{ margin: 0 }}>
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="reg-sensor-code">
                Sensor Code *
              </label>
              <input
                id="reg-sensor-code"
                type="text"
                className="form-control mono"
                value={sensorCode}
                onChange={(e) => setSensorCode(e.target.value)}
                placeholder="e.g., LOGICAL-SENSOR-01"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-sensor-name">
                Sensor Name *
              </label>
              <input
                id="reg-sensor-name"
                type="text"
                className="form-control"
                value={sensorName}
                onChange={(e) => setSensorName(e.target.value)}
                placeholder="e.g., Logical sensor_01"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-sensor-kind">
                Sensor Kind *
              </label>
              <input
                id="reg-sensor-kind"
                type="text"
                className="form-control"
                value={sensorKind}
                onChange={(e) => setSensorKind(e.target.value)}
                placeholder="e.g., cmapss_channel or pressure_transducer"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-channel-id">
                Logical Channel Assignment
              </label>
              <select
                id="reg-channel-id"
                className="form-control mono"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
              >
                {Array.from({ length: 21 }).map((_, idx) => {
                  const ch = `sensor_${String(idx + 1).padStart(2, '0')}`;
                  return <option key={ch} value={ch}>{ch}</option>;
                })}
              </select>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Map Sensor Channel */}
      {isInstallOpen && (
        <Modal
          isOpen={isInstallOpen}
          onClose={() => setIsInstallOpen(false)}
          title="Map Sensor to Channel Slot"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsInstallOpen(false)}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="install-sensor-form"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Mapping...' : 'Confirm Mapping'}
              </button>
            </>
          }
        >
          <form id="install-sensor-form" onSubmit={handleInstallSensor} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
            {formError && (
              <div className="alert alert-danger" style={{ margin: 0 }}>
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="inst-sensor-select">
                Sensor to Map *
              </label>
              <select
                id="inst-sensor-select"
                className="form-control"
                value={installSensorId}
                onChange={(e) => setInstallSensorId(e.target.value)}
                required
              >
                {sensors.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.sensor_code} ({s.name})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="inst-channel-select">
                Channel Slot *
              </label>
              <select
                id="inst-channel-select"
                className="form-control mono"
                value={installChannel}
                onChange={(e) => setInstallChannel(e.target.value)}
                required
              >
                {Array.from({ length: 21 }).map((_, idx) => {
                  const ch = `sensor_${String(idx + 1).padStart(2, '0')}`;
                  return <option key={ch} value={ch}>{ch}</option>;
                })}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="inst-note">
                Installation Note (optional)
              </label>
              <input
                id="inst-note"
                type="text"
                className="form-control"
                value={installNote}
                onChange={(e) => setInstallNote(e.target.value)}
                placeholder="e.g., Logical demo channel binding"
              />
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
