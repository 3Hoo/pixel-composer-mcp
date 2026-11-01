# 기능 지도 (Pixel Composer 1.22.0.5)

하고 싶은 일 → 쓸 만한 노드. 선택지이지 정답이 아니다. 노드 타입 이름(`Node_*`)은 `add_node`에 그대로 쓴다. 입력 번호는 `describe_node`로 확인한다(버전마다 다름).

표시:
- ✅ MCP로 만들고 출력까지 확인함
- 🔹 MCP로 생성은 확인함, 결과물은 아직 안 봄
- ⚠️ 미검증. 처음 쓸 때 작은 테스트 프로젝트로 먼저 확인한다
- ⛔ 쓰지 말 것

## 형태 그리기
| 노드 | 용도 |
|---|---|
| ✅ `Node_Shape` | 원·사각·삼각·사각형(4점) 등 SDF 도형. Positioning Mode `Full Image`(15=2)면 점 좌표가 캔버스 픽셀. BG Surface(1=2, 46)로 여러 도형을 겹쳐 쌓는다 |
| ⚠️ `Node_Shape_Polygon` | 다각형, 별 |
| ⚠️ `Node_Line`, `Node_Line_2Points` | 선, 경로를 따라 그리는 선 |
| ⚠️ `Node_Path_Profile`, `Node_Ribbon` | 경로 한쪽 채우기, 리본 |
| ⚠️ `Node_Text` | 글자 |
| ⚠️ `Node_Gradient`, `Node_Gradient_Points` | 그라데이션 이미지 |

## 완성형 생성기 (MKFX)
입력이 적고 바로 쓸 만한 결과를 낸다. 대부분 흑백이나 단색이라 `Node_Colorize`나 팔레트로 색을 입힌다.

| 노드 | 용도 |
|---|---|
| ✅ `Node_MK_Flame` | 불꽃·폭발 형태 애니메이션. 흑백 출력이라 색은 따로 입힌다 |
| ⚠️ `Node_MK_Smoke`, `Node_MK_Cloud` | 연기, 구름 |
| ⚠️ `Node_MK_Sparkle`, `Node_MK_Blinker` | 반짝임, 깜빡임 |
| ⚠️ `Node_MK_Rain`, `Node_MK_Fall`, `Node_MK_Flake`, `Node_MK_Drip` | 비, 낙엽, 눈송이, 물방울 |
| ⚠️ `Node_MK_Saber`, `Node_MK_GodRay`, `Node_MK_Flare` | 광선검, 빛줄기, 렌즈 플레어 |
| ⚠️ `Node_MK_Rock`, `Node_MK_Grass`, `Node_MK_Tile` | 바위, 풀, 엔진용 타일셋 |
| ⚠️ `Node_MK_Fracture` | 이미지 조각내기 + 간단한 물리 |

## 질감과 패턴
| 노드 | 용도 |
|---|---|
| ✅ `Node_Perlin` (Tile=4 켜면 이음매 없음), ⚠️ `Node_Noise_Simplex`, `Node_Cellular`, `Node_Flow_Noise`, `Node_Shard_Noise`, `Node_Caustic`, `Node_Crack_Pattern` | 노이즈. 재질 표면, 마스크, 왜곡 맵 |
| ⚠️ `Node_Grid`, `Node_Grid_Hex`, `Node_Checker`, `Node_Stripe`, `Node_Random_Tile`, `Node_Herringbone_Tile` | 반복 패턴, 바닥·벽 타일 |
| ⚠️ `Node_Sky` | 하늘 배경 |

## 3D로 만들어 픽셀로 렌더
| 노드 | 용도 |
|---|---|
| ⚠️ `Node_3D_Mesh_Cube`/`_Cylinder`/`_Sphere_UV`/`_Cone`/`_Torus`, `Node_3D_Camera`, `Node_3D_Light_Directional` | 단순 입체를 원하는 각도로 렌더 → 픽셀화. 아이콘의 기본 형태 |
| ⚠️ `Node_3D_Mesh_Extrude` | 2D 이미지를 두께 있는 3D로 |
| ⚠️ `Node_Sprite_Stack` | 스프라이트 스택(층을 쌓은 가짜 3D) |
| ⚠️ `Node_Normal`, `Node_Normal_Light`, `Node_Bevel`, `Node_Ambient_Occlusion` | 높이 → 노멀 → 조명. 평면 그림에 입체감과 일관된 빛 방향 |

## 파티클
| 노드 | 용도 |
|---|---|
| ✅ `Node_Particle` | 단일 노드 파티클. 스폰은 스트림 + `27` 스위치 키프레임(→ pitfalls) |
| ⛔ `Node_VFX_Group_Inline` (VFX 그룹, 힘 노드) | 1.22.0.5에서 MCP로 만든 그룹은 렌더할 때 앱 에러(`surface_wcache`)가 났다. 스프라이트를 연결해도 같다. 원인 미확인 |
| ⚠️ `Node_pSystem_Inline` | 신형 파티클 시스템. 그룹형이라 VFX 그룹과 같은 문제가 있는지 먼저 확인 |

## 물리 시뮬레이션 (그룹형, ⚠️ 전부 미검증)
`Node_Smoke_Group_Inline`(연기), `Node_FLIP_Group_Inline`(유체), `Node_Rigid_Group_Inline`(강체), `Node_GrainSim_Inline`(모래), `Node_Strand_Group_Inline`(털), `Node_VerletSim_Inline`(천). 그룹형이므로 VFX 그룹처럼 렌더 에러가 나는지 먼저 확인한다.

## 움직임
| 노드 / 방법 | 용도 |
|---|---|
| ✅ 키프레임 (`set_keyframes`, `Graph.anim`) | 모든 입력을 프레임별로 |
| ⚠️ `Node_Wiggler`, `Node_Fn_WaveTable`, `Node_Fn_Ease` | 흔들림, 주기 운동, 이징 값 |
| ⚠️ `Node_Delay`, `Node_Stagger` | 시차 |
| ⚠️ `Node_Mesh_Warp`, `Node_Puppet_Warp`, `Node_Bend` | 이미지 변형 애니메이션 |
| ⚠️ `Node_Trail`, `Node_Smear`, `Node_Time_Remap` | 잔상, 번짐 |

## 리깅 (Armature)
| 노드 | 용도 |
|---|---|
| ✅ `Node_Armature` | 뼈 구조. 노드 JSON의 `bones` 트리로 저장되어 파일 편집으로 만들 수 있다 (→ character-rig.md) |
| ✅ `Node_Armature_Pose` | 뼈마다 변형 입력이 자동 생성됨(3번부터). 키프레임으로 포즈 애니메이션 |
| ✅ `Node_Armature_Bind` | 레이어 그림을 뼈에 붙여 렌더. 레이어↔뼈 연결은 `attri.boneIDMap` |
| ⚠️ `Node_Armature_IK`, `Node_Armature_Human`, `Node_Armature_Mesh_Rig` | IK, 사람형 프리셋, 메쉬 변형 리깅 |

## 픽셀아트로 다듬기
| 노드 | 용도 |
|---|---|
| ✅ `Node_Threshold` (알파 모드) | 알파를 0/255로. 반투명 가장자리 제거 |
| ✅ `Node_Posterize` (팔레트 모드) | 지정 팔레트로 색 고정. 알파 마스크 필요 (→ pitfalls) |
| ✅ `Node_De_Stray` | 떨어진 픽셀 제거 |
| ✅ `Node_Alpha_Grey` | 알파 → 흑백 마스크 |
| ⚠️ `Node_De_Corner` | 계단 모서리 정리 |
| ✅ `Node_Outline` | 외곽선. 너비 1, 안티앨리어싱(6) 끄기 |
| ⚠️ `Node_Color_replace`, `Node_Palette_Extract`, `Node_Palette_Shrink` | 팔레트 추출·축소·교체 |
| ⚠️ `Node_Dither`, `Node_Bit_Reduce` | 디더, 색 양자화 |
| ⚠️ `Node_Scale_Algo`, `Node_Downscale` | 픽셀아트용 확대·축소 |
| ⚠️ `Node_Pixel_Cloud`, `Node_Shadow`, `Node_2D_light` | 픽셀 흩뿌리기, 그림자, 2D 조명 |

## 일러스트·후처리
| 노드 | 용도 |
|---|---|
| ✅ `Node_Blur` | 부드럽게. 6 초과는 위쪽 행으로 감김 (→ pitfalls) |
| ✅ `Node_Bloom`, `Node_Level` | 빛 번짐, 알파·밝기 범위 자르기 |
| ✅ `Node_Colorize` | 밝기 → 그라데이션 색(1). 흑백 생성기·노이즈에 색 입히기. 뒤에 팔레트 Posterize로 색 고정 |
| ⚠️ `Node_Glow`, `Node_Color_adjust`, `Node_Curve` | 외곽 발광, 색 조정 |

## 합성과 출력
| 노드 | 용도 |
|---|---|
| ✅ `Node_Render_Sprite_Sheet` | 애니메이션 → 시트. 두 번 export 필요 (→ pitfalls) |
| ✅ `Node_Export` | PNG/GIF/시퀀스. MCP가 템플릿으로 만든다 |
| ⚠️ `Node_Blend`, `Node_Composite`, `Node_Stack`, `Node_Image_Grid` | 레이어 합성, 나란히 붙이기 |
| ⚠️ `Node_Tile_Tileset`, `Node_Tile_Rule`, `Node_Tile_Render`, `Node_Tile_Tilemap_Export` | 타일셋, 오토타일 규칙, 타일맵 출력 |
| ✅ `Node_Offset` (X·Y 0.5) | 반 칸 밀어 이음매 확인 |
| ⚠️ `Node_Blend_Edge` | 반복 안 되는 그림을 이음매 없게 섞기 |

## 입력
| 노드 | 용도 |
|---|---|
| ✅ `Node_ASE_File_Read` | Aseprite 파일. `add_node(..., file=<경로>)`로 만든다. 출력 0 = 합친 그림. 레이어별 출력은 "Generate Layers" |
| 🔹 `Node_Image`, `Node_Image_gif`, `Node_PXC` 등 파일 노드 | 같은 방식(`file=`)으로 생성. ASE 외에는 결과물 미확인 |
| ⛔ `Node_Pixel_Builder` | 툴팁에 "Will break, do not create" |

## 목록 다시 뽑기
노드 목록과 툴팁은 설치 폴더의 데이터에 있다: `%LOCALAPPDATA%\PixelComposer\Nodes\Internal\<카테고리>\<Node_*>\info.json`. 버전이 바뀌면 여기서 다시 확인한다. 이 지도에 없는 노드도 많다(총 968개).

```python
import json, os, re
from pathlib import Path
root = Path(os.environ["LOCALAPPDATA"]) / "PixelComposer/Nodes/Internal"
for f in sorted(root.rglob("info.json")):
    j = json.loads(re.sub(r",(\s*[}\]])", r"\1", re.sub(r"//[^\n]*", "", f.read_text("utf-8", "replace"))))
    print(f.parent.parent.name, j.get("baseNode"), "-", j.get("tooltip", ""))
```
