import { useRef, useState, useCallback, useEffect, useMemo } from 'react';
import type { MutableRefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useTexture, Html, Billboard } from '@react-three/drei';
import * as THREE from 'three';
import type { SpaceNode } from './types';

// ── Panorama Sphere ───────────────────────────────────────────────────────────

function PanoramaSphere({ imageUrl, depthMap, depthWidth, depthHeight, displacement }: {
  imageUrl: string;
  depthMap: Float32Array;
  depthWidth: number;
  depthHeight: number;
  displacement: number;
}) {
  const texture = useTexture(imageUrl);

  useEffect(() => {
    texture.wrapS = THREE.RepeatWrapping;
    texture.repeat.x = -1;
    texture.needsUpdate = true;
  }, [texture]);

  const geometry = useMemo(() => {
    const geo = new THREE.SphereGeometry(10, 128, 64);
    const pos = geo.attributes.position;
    const count = pos.count;

    let dMin = Infinity, dMax = -Infinity;
    for (let i = 0; i < depthMap.length; i++) {
      if (depthMap[i] < dMin) dMin = depthMap[i];
      if (depthMap[i] > dMax) dMax = depthMap[i];
    }
    const dRange = dMax - dMin || 1;

    for (let i = 0; i < count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const z = pos.getZ(i);
      const u = 0.5 + Math.atan2(z, x) / (2 * Math.PI);
      const v = 0.5 - Math.asin(y / 10) / Math.PI;
      const px = Math.min(Math.floor(u * depthWidth), depthWidth - 1);
      const py = Math.min(Math.floor(v * depthHeight), depthHeight - 1);
      const idx = py * depthWidth + px;
      const d = idx >= 0 && idx < depthMap.length ? (depthMap[idx] - dMin) / dRange : 0;
      const disp = (d * 2 - 1) * displacement;
      const len = Math.sqrt(x * x + y * y + z * z);
      pos.setXYZ(i, x + (x / len) * disp, y + (y / len) * disp, z + (z / len) * disp);
    }

    geo.computeVertexNormals();
    return geo;
  }, [depthMap, depthWidth, depthHeight, displacement]);

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial map={texture} side={THREE.BackSide} />
    </mesh>
  );
}

// ── Click Target Sphere (for edit mode raycasting) ────────────────────────────

function ClickTargetSphere({ onHit }: { onHit: (pos: THREE.Vector3) => void }) {
  return (
    <mesh
      onPointerDown={(e) => { e.stopPropagation(); onHit(e.point); }}
    >
      <sphereGeometry args={[9.5, 64, 32]} />
      <meshBasicMaterial transparent opacity={0} side={THREE.BackSide} depthWrite={false} />
    </mesh>
  );
}

// ── Navigation Pin ────────────────────────────────────────────────────────────

function NavigationPin({ position, label, isEditing, isHidden, onClick }: {
  position: [number, number, number];
  label: string;
  isEditing: boolean;
  isHidden?: boolean;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const ringRef = useRef<THREE.Mesh>(null);
  const { gl } = useThree();

  useEffect(() => {
    if (isEditing) {
      gl.domElement.style.cursor = 'crosshair';
    } else {
      gl.domElement.style.cursor = hovered ? 'pointer' : 'auto';
    }
    return () => { gl.domElement.style.cursor = 'auto'; };
  }, [hovered, isEditing, gl]);

  useFrame((_, delta) => {
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * (isEditing ? 4 : hovered ? 3 : 0.8);
    }
  });

  const color = isEditing ? '#ffcc00' : isHidden ? '#888888' : hovered ? '#ffffff' : '#00e5ff';
  const baseOpacity = isHidden ? 0.3 : 1;

  // Billboard always faces the camera regardless of pin position on the sphere.
  // depthTest={false} prevents displaced sphere geometry from occluding the pin.
  return (
    <Billboard position={position} follow>
      {/* Rotating arc ring */}
      <mesh ref={ringRef}>
        <ringGeometry args={[0.48, 0.65, 48, 1, 0, Math.PI * 1.6]} />
        <meshBasicMaterial color={color} transparent opacity={(isEditing ? 1 : hovered ? 1 : 0.85) * baseOpacity} side={THREE.DoubleSide} depthTest={false} />
      </mesh>

      {/* Clickable center disc */}
      <mesh
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <circleGeometry args={[0.45, 40]} />
        <meshBasicMaterial
          color={isEditing ? '#332200' : hovered ? '#004488' : '#001a33'}
          transparent opacity={(hovered || isEditing ? 0.95 : 0.7) * baseOpacity}
          side={THREE.DoubleSide} depthTest={false}
        />
      </mesh>

      {/* Center icon */}
      <mesh position={[0, 0.32, 0]}>
        <coneGeometry args={[0.14, 0.28, 3]} />
        <meshBasicMaterial color={color} transparent opacity={0.9 * baseOpacity} side={THREE.DoubleSide} depthTest={false} />
      </mesh>

      {/* Label */}
      <Html position={[0, 0.95, 0]} center distanceFactor={8}>
        <div className={`pin-label${hovered ? ' hovered' : ''}${isEditing ? ' editing' : ''}${isHidden ? ' hidden-pin' : ''}`}>
          {isEditing ? `✎ ${label}` : isHidden ? `👁‍🗨 ${label}` : label}
        </div>
      </Html>
    </Billboard>
  );
}

// ── Default pin positions ─────────────────────────────────────────────────────

function getDefaultPosition(index: number, total: number): [number, number, number] {
  const r = 5, y = -1.8;
  const angle = (index * Math.PI * 2) / total - Math.PI / 2;
  return [r * Math.cos(angle), y, r * Math.sin(angle)];
}

// ── Gyroscope helpers ─────────────────────────────────────────────────────────

// DeviceOrientation → camera quaternion（標準VRパノラマ変換）
const _gyroQ0 = new THREE.Quaternion();
const _gyroQ1 = new THREE.Quaternion(-Math.sqrt(0.5), 0, 0, Math.sqrt(0.5));
const _gyroZee = new THREE.Vector3(0, 0, 1);
const _gyroEuler = new THREE.Euler();

function applyDeviceOrientation(
  camera: THREE.Camera,
  alpha: number, beta: number, gamma: number,
  screenAngle: number,
) {
  _gyroEuler.set(
    THREE.MathUtils.degToRad(beta),
    THREE.MathUtils.degToRad(alpha),
    THREE.MathUtils.degToRad(-gamma),
    'YXZ',
  );
  camera.quaternion.setFromEuler(_gyroEuler);
  camera.quaternion.multiply(_gyroQ1);
  _gyroQ0.setFromAxisAngle(_gyroZee, -THREE.MathUtils.degToRad(screenAngle));
  camera.quaternion.multiply(_gyroQ0);
}

// ── Scene Controller ──────────────────────────────────────────────────────────

function SceneController({
  isTransitioningRef,
  movingTowardRef,
  shouldResetCameraRef,
  editModeRef,
  gyroModeRef,
  orientationRef,
}: {
  isTransitioningRef: MutableRefObject<boolean>;
  movingTowardRef: MutableRefObject<THREE.Vector3 | null>;
  shouldResetCameraRef: MutableRefObject<boolean>;
  editModeRef: MutableRefObject<boolean>;
  gyroModeRef: MutableRefObject<boolean>;
  orientationRef: MutableRefObject<{ alpha: number; beta: number; gamma: number } | null>;
}) {
  const { camera, gl } = useThree();
  const isDragging = useRef(false);
  const prev = useRef({ x: 0, y: 0 });
  const spherical = useRef({ theta: 0, phi: Math.PI / 2 });
  const radius = useRef(0.001);

  useEffect(() => {
    const dom = gl.domElement;

    const onDown = (e: MouseEvent) => {
      if (isTransitioningRef.current || editModeRef.current || gyroModeRef.current) return;
      isDragging.current = true;
      prev.current = { x: e.clientX, y: e.clientY };
    };
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current || isTransitioningRef.current || editModeRef.current) return;
      const dx = e.clientX - prev.current.x;
      const dy = e.clientY - prev.current.y;
      prev.current = { x: e.clientX, y: e.clientY };
      spherical.current.theta -= dx * 0.005;
      spherical.current.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.current.phi - dy * 0.005));
    };
    const onUp = () => { isDragging.current = false; };
    const onWheel = (e: WheelEvent) => {
      if (isTransitioningRef.current || editModeRef.current) return;
      radius.current = Math.max(0.001, Math.min(8, radius.current + e.deltaY * 0.01));
    };
    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length !== 1 || editModeRef.current || gyroModeRef.current) return;
      isDragging.current = true;
      prev.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    };
    const onTouchMove = (e: TouchEvent) => {
      if (!isDragging.current || e.touches.length !== 1 || editModeRef.current) return;
      const dx = e.touches[0].clientX - prev.current.x;
      const dy = e.touches[0].clientY - prev.current.y;
      prev.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      spherical.current.theta -= dx * 0.005;
      spherical.current.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.current.phi - dy * 0.005));
    };
    const onTouchEnd = () => { isDragging.current = false; };

    dom.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    dom.addEventListener('wheel', onWheel, { passive: true });
    dom.addEventListener('touchstart', onTouchStart, { passive: true });
    dom.addEventListener('touchmove', onTouchMove, { passive: true });
    dom.addEventListener('touchend', onTouchEnd);

    return () => {
      dom.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      dom.removeEventListener('wheel', onWheel);
      dom.removeEventListener('touchstart', onTouchStart);
      dom.removeEventListener('touchmove', onTouchMove);
      dom.removeEventListener('touchend', onTouchEnd);
    };
  }, [gl, isTransitioningRef, editModeRef, gyroModeRef]);

  useFrame((_, delta) => {
    if (shouldResetCameraRef.current) {
      spherical.current = { theta: 0, phi: Math.PI / 2 };
      radius.current = 0.001;
      movingTowardRef.current = null;
      shouldResetCameraRef.current = false;
    }

    if (isTransitioningRef.current && movingTowardRef.current) {
      camera.position.lerp(movingTowardRef.current, delta * 5);
      camera.lookAt(0, 0, 0);
    } else if (gyroModeRef.current && orientationRef.current) {
      camera.position.set(0, 0, 0.001);
      const { alpha, beta, gamma } = orientationRef.current;
      const screenAngle =
        (screen.orientation?.angle) ??
        ((window as unknown as { orientation?: number }).orientation ?? 0);
      applyDeviceOrientation(camera, alpha, beta, gamma, screenAngle);
    } else {
      const { theta, phi } = spherical.current;
      const r = radius.current;
      camera.position.set(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta),
      );
      camera.lookAt(0, 0, 0);
    }
  });

  return null;
}

// ── PanoramaViewer ────────────────────────────────────────────────────────────

export interface PanoramaViewerProps {
  currentNode: SpaceNode;
  otherNodes: SpaceNode[];
  displacement: number;
  onDisplacementChange: (v: number) => void;
  onNavigate: (nodeId: string) => void;
  pinPositions: Record<string, [number, number, number]>;
  onPinPositionChange: (fromId: string, toId: string, pos: [number, number, number]) => void;
  onPinPositionReset: (fromId: string, toId: string) => void;
  hiddenLinks?: Record<string, boolean>;
  onHiddenLinksChange?: (fromId: string, toId: string, hidden: boolean) => void;
  readOnly?: boolean;
}

export default function PanoramaViewer({
  currentNode,
  otherNodes,
  displacement,
  onDisplacementChange,
  onNavigate,
  pinPositions,
  onPinPositionChange,
  onPinPositionReset,
  hiddenLinks = {},
  onHiddenLinksChange,
  readOnly = false,
}: PanoramaViewerProps) {
  const [fadeOpacity, setFadeOpacity] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [editTargetId, setEditTargetId] = useState<string | null>(null);
  const [gyroEnabled, setGyroEnabled] = useState(false);

  const isTransitioningRef = useRef(false);
  const movingTowardRef = useRef<THREE.Vector3 | null>(null);
  const shouldResetCameraRef = useRef(false);
  const editModeRef = useRef(false);
  const gyroModeRef = useRef(false);
  const orientationRef = useRef<{ alpha: number; beta: number; gamma: number } | null>(null);

  // Keep refs in sync with state for use inside Three.js frame loop
  useEffect(() => { editModeRef.current = editMode; }, [editMode]);
  useEffect(() => { gyroModeRef.current = gyroEnabled; }, [gyroEnabled]);

  // DeviceOrientation listener
  useEffect(() => {
    if (!gyroEnabled) { orientationRef.current = null; return; }
    const handler = (e: DeviceOrientationEvent) => {
      if (e.alpha !== null && e.beta !== null && e.gamma !== null) {
        orientationRef.current = { alpha: e.alpha, beta: e.beta, gamma: e.gamma };
      }
    };
    window.addEventListener('deviceorientation', handler, true);
    return () => window.removeEventListener('deviceorientation', handler, true);
  }, [gyroEnabled]);

  const handleGyroToggle = useCallback(async () => {
    if (gyroEnabled) { setGyroEnabled(false); return; }
    // iOS 13+ requires explicit permission
    const DOE = DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> };
    if (typeof DOE.requestPermission === 'function') {
      try {
        const result = await DOE.requestPermission();
        if (result === 'granted') setGyroEnabled(true);
        else alert('センサーの使用が許可されませんでした');
      } catch {
        alert('センサーの許可リクエストに失敗しました');
      }
    } else {
      setGyroEnabled(true);
    }
  }, [gyroEnabled]);

  const allOtherNodes = otherNodes;
  // 非表示フィルタ: editModeは全ピン表示（位置調整のため）、通常モードは非表示を除外
  const visibleOtherNodes = editMode
    ? allOtherNodes
    : allOtherNodes.filter(n => !hiddenLinks[`${currentNode.id}::${n.id}`]);

  // Get position for a specific target node (custom or default)
  const getPinPosition = useCallback((toNodeId: string, index: number): [number, number, number] => {
    const key = `${currentNode.id}::${toNodeId}`;
    return pinPositions[key] ?? getDefaultPosition(index, allOtherNodes.length);
  }, [currentNode.id, pinPositions, allOtherNodes.length]);

  // Enter edit mode for a specific pin
  const handleEditPin = useCallback((nodeId: string) => {
    setEditMode(true);
    setEditTargetId(nodeId);
  }, []);

  const handleExitEdit = useCallback(() => {
    setEditMode(false);
    setEditTargetId(null);
  }, []);

  // Called when user clicks on the sphere in edit mode
  const handleSphereClick = useCallback((point: THREE.Vector3) => {
    if (!editMode || !editTargetId) return;
    const pos: [number, number, number] = [point.x, point.y, point.z];
    onPinPositionChange(currentNode.id, editTargetId, pos);
  }, [editMode, editTargetId, currentNode.id, onPinPositionChange]);

  // Called when user clicks a pin in navigation mode
  const handlePinClick = useCallback((nodeId: string, pinPos: [number, number, number]) => {
    if (editMode) {
      // In edit mode, clicking a pin selects it for editing
      setEditTargetId(nodeId);
      return;
    }
    if (isTransitioningRef.current) return;
    isTransitioningRef.current = true;

    movingTowardRef.current = new THREE.Vector3(...pinPos).multiplyScalar(0.32);

    const t1 = setTimeout(() => setFadeOpacity(1), 370);
    const t2 = setTimeout(() => {
      onNavigate(nodeId);
      shouldResetCameraRef.current = true;
    }, 670);
    const t3 = setTimeout(() => setFadeOpacity(0), 900);
    const t4 = setTimeout(() => { isTransitioningRef.current = false; }, 1400);

    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
  }, [editMode, onNavigate]);

  return (
    <div className="viewer-wrap">
      <Canvas
        camera={{ fov: 90, near: 0.001, far: 100, position: [0, 0, 0.001] }}
        style={{ width: '100%', height: '100%', background: '#000' }}
      >
        <PanoramaSphere
          key={currentNode.id}
          imageUrl={currentNode.imageUrl}
          depthMap={currentNode.depthMap!}
          depthWidth={currentNode.depthWidth!}
          depthHeight={currentNode.depthHeight!}
          displacement={displacement}
        />

        {/* Click target for edit mode */}
        {editMode && <ClickTargetSphere onHit={handleSphereClick} />}

        {/* Navigation / edit pins */}
        {visibleOtherNodes.map((node, i) => {
          const pos = getPinPosition(node.id, i);
          const isHidden = !!hiddenLinks[`${currentNode.id}::${node.id}`];
          return (
            <NavigationPin
              key={node.id}
              position={pos}
              label={node.name}
              isEditing={editMode && editTargetId === node.id}
              isHidden={isHidden}
              onClick={() => handlePinClick(node.id, pos)}
            />
          );
        })}

        <SceneController
          isTransitioningRef={isTransitioningRef}
          movingTowardRef={movingTowardRef}
          shouldResetCameraRef={shouldResetCameraRef}
          editModeRef={editModeRef}
          gyroModeRef={gyroModeRef}
          orientationRef={orientationRef}
        />
      </Canvas>

      {/* Fade overlay */}
      <div
        className="fade-overlay"
        style={{
          opacity: fadeOpacity,
          transition: fadeOpacity > 0 ? 'opacity 0.28s ease-in' : 'opacity 0.45s ease-out',
          pointerEvents: fadeOpacity > 0 ? 'auto' : 'none',
        }}
      />

      {/* Gyro toggle — floating bottom-right */}
      {!editMode && (
        <button
          className={`btn-gyro-float${gyroEnabled ? ' active' : ''}`}
          onClick={handleGyroToggle}
          title={gyroEnabled ? 'ジャイロをオフ' : 'スマホの向きで視点操作'}
        >
          {gyroEnabled ? '🔄' : '📱'}
        </button>
      )}

      {/* Controls overlay — 編集モード or 管理画面のみ表示 */}
      {(editMode || !readOnly) && (
      <div className="controls-overlay">
        {!editMode ? (
          <>
            <div className="ctrl-row">
              <span className="ctrl-label">変形量</span>
              <input
                type="range" min={0} max={4} step={0.1}
                value={displacement}
                onChange={e => onDisplacementChange(Number(e.target.value))}
                className="ctrl-slider"
              />
              <span className="ctrl-val">{displacement.toFixed(1)}</span>
            </div>
            {allOtherNodes.length > 0 && (
              <button className="btn-edit-pins" onClick={() => setEditMode(true)}>
                📍 ピン編集
              </button>
            )}
          </>
        ) : (
          <div className="edit-panel">
            <div className="edit-panel-title">
              <span className="edit-badge">編集モード</span>
              <button className="btn-edit-done" onClick={handleExitEdit}>完了</button>
            </div>
            <div className="edit-panel-desc">
              移動先を選んでパノラマ上の好きな場所をクリック
            </div>
            <div className="edit-pin-list">
              {allOtherNodes.map((node) => {
                const isSelected = editTargetId === node.id;
                const hasCustom = !!pinPositions[`${currentNode.id}::${node.id}`];
                const isHidden = !!hiddenLinks[`${currentNode.id}::${node.id}`];
                return (
                  <div key={node.id} className={`edit-pin-item${isSelected ? ' selected' : ''}${isHidden ? ' pin-hidden' : ''}`}>
                    <button
                      className="edit-pin-visibility"
                      title={isHidden ? 'ピンを表示する' : 'ピンを非表示にする'}
                      onClick={() => onHiddenLinksChange?.(currentNode.id, node.id, !isHidden)}
                    >
                      {isHidden ? '🙈' : '👁'}
                    </button>
                    <button
                      className="edit-pin-select"
                      onClick={() => handleEditPin(node.id)}
                    >
                      <span className="edit-pin-dot" style={{ background: isSelected ? '#ffcc00' : isHidden ? '#666' : '#00e5ff' }} />
                      <span className="edit-pin-name">{node.name}</span>
                      {hasCustom && <span className="edit-pin-custom">✓</span>}
                      {isSelected && <span className="edit-pin-arrow">← クリックで配置</span>}
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="edit-pin-hint">
              ピンを初期位置に戻すにはリセットボタンを長押し
            </div>
            <div className="edit-pin-reset-row">
              {allOtherNodes.map((node) => {
                const hasCustom = !!pinPositions[`${currentNode.id}::${node.id}`];
                return (
                  <button
                    key={node.id}
                    className={`edit-pin-reset${hasCustom ? ' has-custom' : ''}`}
                    title={`${node.name} のピンを初期位置に戻す`}
                    disabled={!hasCustom}
                    onClick={() => onPinPositionReset(currentNode.id, node.id)}
                  >
                    ↺ {node.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
