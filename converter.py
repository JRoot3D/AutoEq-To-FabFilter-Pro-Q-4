import re
import math
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class Filter:
    enabled: bool
    filter_type: str  # PK, LSC, HSC, LP, HP
    frequency: float  # Hz
    gain: float  # dB
    q: float


@dataclass
class EQPreset:
    preamp: float  # dB
    filters: List[Filter]
    name: str = ""
    author: str = ""
    tags: str = ""


def parse_text_preset(text: str) -> EQPreset:
    lines = text.strip().split('\n')

    preamp = 0.0
    filters = []

    for line in lines:
        line = line.strip()

        # Parse preamp
        if line.startswith('Preamp:'):
            match = re.search(r'Preamp:\s*(-?\d+\.?\d*)\s*dB', line)
            if match:
                preamp = float(match.group(1))

        # Parse filter
        elif line.startswith('Filter'):
            # Example: Filter 1: ON PK Fc 105 Hz Gain 8.2 dB Q 0.70
            pattern = r'Filter\s+\d+:\s+(ON|OFF)\s+(\w+)\s+Fc\s+(\d+\.?\d*)\s*Hz\s+Gain\s+(-?\d+\.?\d*)\s*dB\s+Q\s+(\d+\.?\d*)'
            match = re.search(pattern, line)

            if match:
                enabled = match.group(1) == 'ON'
                filter_type = match.group(2)
                frequency = float(match.group(3))
                gain = float(match.group(4))
                q = float(match.group(5))

                filters.append(Filter(
                    enabled=enabled,
                    filter_type=filter_type,
                    frequency=frequency,
                    gain=gain,
                    q=q
                ))

    return EQPreset(preamp=preamp, filters=filters)


def frequency_to_proq4(freq_hz: float) -> float:
    return math.log2(freq_hz)


def q_to_proq4(q: float, filter_type: str) -> float:
    Q_MIN = 0.025
    Q_MAX = 40.0

    # Clamp Q to valid range
    q = max(Q_MIN, min(Q_MAX, q))

    # Logarithmic mapping
    normalized = (math.log(q) - math.log(Q_MIN)) / (math.log(Q_MAX) - math.log(Q_MIN))

    return normalized


def filter_type_to_shape(filter_type: str) -> int:
    mapping = {
        'PK': 0,  # Peak/Bell
        'LSC': 1,  # Low Shelf
        'LP': 2,  # Low Cut/High Pass
        'HSC': 3,  # High Shelf
        'HP': 4,  # High Cut/Low Pass
    }
    return mapping.get(filter_type, 0)


def preamp_to_output_level(preamp: float) -> float:
    return preamp / 36.0


def generate_default_band_params(band_num: int, used: bool = False) -> Dict[str, str]:
    params = {
        f'Band {band_num} Used': '1' if used else '0',
        f'Band {band_num} Enabled': '1',
        f'Band {band_num} Frequency': '9.96578407287598',  # ~1000 Hz default
        f'Band {band_num} Gain': '0',
        f'Band {band_num} Q': '0.5',
        f'Band {band_num} Shape': '0',
        f'Band {band_num} Slope': '2',
        f'Band {band_num} Stereo Placement': '2',
        f'Band {band_num} Speakers': '1',
        f'Band {band_num} Dynamic Range': '0',
        f'Band {band_num} Dynamics Enabled': '1',
        f'Band {band_num} Dynamics Auto': '1',
        f'Band {band_num} Threshold': '0.666666686534882' if not used else '1',
        f'Band {band_num} Attack': '50',
        f'Band {band_num} Release': '50',
        f'Band {band_num} External Side Chain': '0',
        f'Band {band_num} Side Chain Filtering': '0',
        f'Band {band_num} Side Chain Low Frequency': '3.32192802429199' if not used else '6.64385604858398',
        f'Band {band_num} Side Chain High Frequency': '14.287712097168' if not used else '11.5507469177246',
        f'Band {band_num} Side Chain Audition': '0',
        f'Band {band_num} Spectral Enabled': '0',
        f'Band {band_num} Spectral Density': '50',
        f'Band {band_num} Solo': '0',
    }
    return params


def eq_preset_to_ffp(preset: EQPreset) -> str:
    lines = []

    # Header section
    lines.append('[Preset]')
    lines.append('Signature=FQ4p')
    lines.append('Version=4')
    lines.append(f'Author={preset.author or ""}')
    lines.append(f'Tags={preset.tags or ""}')
    lines.append('')

    # Parameters section
    lines.append('[Parameters]')

    # Generate parameters for all 24 bands
    for i in range(1, 25):
        if i <= len(preset.filters):
            # Active filter
            filt = preset.filters[i - 1]
            params = generate_default_band_params(i, used=True)

            # Override with actual filter values
            params[f'Band {i} Used'] = '1'
            params[f'Band {i} Enabled'] = '1' if filt.enabled else '0'
            params[f'Band {i} Frequency'] = str(frequency_to_proq4(filt.frequency))
            params[f'Band {i} Gain'] = str(filt.gain)
            params[f'Band {i} Q'] = str(q_to_proq4(filt.q, filt.filter_type))
            params[f'Band {i} Shape'] = str(filter_type_to_shape(filt.filter_type))
        else:
            # Unused band - use defaults
            params = generate_default_band_params(i, used=False)

        # Write all parameters for this band
        for key in sorted(params.keys(), key=lambda x: (int(re.search(r'Band (\d+)', x).group(1)), x)):
            lines.append(f'{key}={params[key]}')

    # Global parameters
    lines.append('Processing Mode=0')
    lines.append('Processing Resolution=1')
    lines.append('Character=0')
    lines.append('Gain Scale=1')
    lines.append(f'Output Level={preamp_to_output_level(preset.preamp)}')
    lines.append('Output Pan=0')
    lines.append('Output Pan Mode=0')
    lines.append('Bypass=0')
    lines.append('Output Invert Phase=0')
    lines.append('Auto Gain=0')

    # Analyzer settings
    lines.append('Analyzer Show Pre-Processing=1')
    lines.append('Analyzer Show Post-Processing=1')
    lines.append('Analyzer Show External Spectrum=1')
    lines.append('Analyzer External Spectrum=-1')
    lines.append('Analyzer Range=2')
    lines.append('Analyzer Resolution=3')
    lines.append('Analyzer Speed=2')
    lines.append('Analyzer Tilt=0')
    lines.append('Analyzer Freeze=0')
    lines.append('Analyzer Show Collisions=0')
    lines.append('Spectrum Grab=0')
    lines.append('Display Range=2')
    lines.append('Receive Midi=0')
    lines.append('Solo Gain=0')

    # Spectral Tilt parameters for all bands
    for i in range(1, 25):
        if i <= len(preset.filters):
            lines.append(f'Band {i} Spectral Tilt=1')
        else:
            lines.append(f'Band {i} Spectral Tilt=0')

    lines.append('')  # Empty line at end

    return '\n'.join(lines)


def convert_text_to_ffp(input_text: str, output_file: str, author: str = "", tags: str = ""):
    # Parse input text
    preset = parse_text_preset(input_text)
    preset.author = author
    preset.tags = tags

    # Convert to FFP format
    ffp_content = eq_preset_to_ffp(preset)

    # Write to the file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(ffp_content)

    print(f"✓ Converted preset saved to: {output_file}")
    print(f"  - Preamp: {preset.preamp} dB")
    print(f"  - Filters: {len(preset.filters)}")


if __name__ == '__main__':
    work_dir_path = Path('results')
    output_dir_path = Path('presets')

    if not work_dir_path.exists():
        print(f"Error: {work_dir_path} directory not found")
        exit(1)

    output_dir_path.mkdir(parents=True, exist_ok=True)

    parametric_eq_files = list(work_dir_path.rglob('*ParametricEQ.txt'))

    if not parametric_eq_files:
        print("No *ParametricEQ.txt files found in work folder")
        exit(0)

    print(f"Found {len(parametric_eq_files)} ParametricEQ.txt files\n")

    # Convert each file
    converted_count = 0
    failed_count = 0

    for input_file in parametric_eq_files:
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                input_text = f.read()

            output_filename = input_file.stem.replace(' ParametricEQ', '') + '.ffp'
            output_file = output_dir_path / output_filename

            device_name = input_file.parent.name

            convert_text_to_ffp(
                input_text=input_text,
                output_file=str(output_file),
                author='JRoot3D',
                tags='Calibration'
            )

            converted_count += 1
            print()

        except Exception as e:
            print(f"✗ Failed to convert {input_file}: {str(e)}\n")
            failed_count += 1

    # Summary
    print("=" * 60)
    print(f"Conversion complete!")
    print(f"  ✓ Converted: {converted_count}")
    if failed_count > 0:
        print(f"  ✗ Failed: {failed_count}")