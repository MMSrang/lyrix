# Bundled AI Models – Provenance & Licenses

Lyrix ships (or downloads into its AI pack) the following third-party model
weights. All of them are redistributable under their respective licenses;
attribution and license texts are reproduced below.

| File | Purpose | Origin | License | SHA256 |
|------|---------|--------|---------|--------|
| `models/segmentation-3.0.bin` | Speaker segmentation (pyannote) | [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) | MIT | `da85c29829d4002daedd676e012936488234d9255e65e86dfab9bec6b1729298` |
| `models/wespeaker-voxceleb-resnet34-LM.bin` | Speaker embedding (pyannote/wespeaker) | [pyannote/wespeaker-voxceleb-resnet34-LM](https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM) | CC-BY-4.0 | `366edf44f4c80889a3eb7a9d7bdf02c4aede3127f7dd15e274dcdb826b143c56` |
| `models/cnn14_16k.pt` | Sound event tagging (PANNs Cnn14, 16 kHz) | [Zenodo record 3987831](https://zenodo.org/records/3987831) (`Cnn14_16k_mAP=0.438.pth`) | CC-BY-4.0 | `4eb1da8c27cdc424813f3107290ca03eabe6142b2807d73e280b804c4a2f245d` |

Whisper speech-recognition models are **not** bundled; they are downloaded at
first use from the official [Systran faster-whisper
repositories](https://huggingface.co/Systran) (MIT).

## Notes on pyannote/segmentation-3.0 (gated access vs. MIT license)

The official Hugging Face repository is *gated*: downloading from HF requires
an account and accepting a usage prompt (contact-information collection by
the authors). The model **weights themselves are MIT-licensed** (see the
`license: mit` field of the model card), which explicitly permits
redistribution. Lyrix therefore ships a byte-identical copy of the official
file — the SHA256 above matches the official Git-LFS object of
`pytorch_model.bin` in the upstream repository, so provenance is verifiable.

Be aware that obtaining the file from this repository instead of Hugging Face
bypasses the authors' contact-information gate. If you prefer to go through
the official flow (and support pyannote's usage statistics), delete
`models/segmentation-3.0.bin` and enter a Hugging Face token in
*Settings → Advanced*; Lyrix will then download the pipeline from the
official gated repositories instead.

The conversion of `Cnn14_16k_mAP=0.438.pth` to `cnn14_16k.pt` is a pure
format conversion (tensor-only checkpoint, fp16 storage for ≥2-D tensors);
no weights were retrained or altered semantically.

## Attribution

- **pyannote.audio** — Hervé Bredin et al.,
  "pyannote.audio: neural building blocks for speaker diarization"
  (ICASSP 2020) and "Powerset multi-class cross entropy loss for neural
  speaker diarization" (Interspeech 2023). MIT License,
  © CNRS / Hervé Bredin.
- **WeSpeaker** — Hongji Wang et al., "Wespeaker: A research and production
  oriented speaker embedding learning toolkit" (ICASSP 2023). CC-BY-4.0,
  packaged for pyannote by the pyannote team.
- **PANNs** — Qiuqiang Kong, Yin Cao, Turab Iqbal, Yuxuan Wang, Wenwu Wang,
  Mark D. Plumbley, "PANNs: Large-Scale Pretrained Audio Neural Networks for
  Audio Pattern Recognition" (IEEE/ACM TASLP 2020). Weights CC-BY-4.0 via
  Zenodo; original code Apache-2.0.
- **AudioSet class labels** (`models/audioset_labels.csv`) — from the
  [audioset_tagging_cnn](https://github.com/qiuqiangkong/audioset_tagging_cnn)
  repository (Apache-2.0), based on Google AudioSet (CC-BY-4.0).
