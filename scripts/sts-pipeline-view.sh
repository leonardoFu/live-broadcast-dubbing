#!/bin/bash
# STS Pipeline Results Viewer
# Shows only key pipeline results: ASR -> Translation -> TTS

echo "🎯 STS Pipeline Results (Ctrl+C to exit)"
echo "========================================="
echo ""

docker logs -f full-sts-service 2>&1 | while read line; do
  # Extract fragment sequence number
  if [[ $line =~ sequence_number=([0-9]+) ]]; then
    seq="${BASH_REMATCH[1]}"
  fi

  # ASR completed (capture latency)
  if [[ $line =~ "asr_completed" ]] && [[ $line =~ latency_ms=([0-9]+) ]]; then
    asr_latency="${BASH_REMATCH[1]}"
  fi

  # ASR result
  if [[ $line =~ "ASR total_text: '"([^\']*)"'" ]]; then
    text="${BASH_REMATCH[1]}"
    if [[ -z "$text" ]]; then
      echo -e "\n📦 Segment $seq"
      echo "   🎤 ASR: (empty - no speech) [${asr_latency}ms]"
    else
      echo -e "\n📦 Segment $seq"
      echo "   🎤 ASR: \"$text\" [${asr_latency}ms]"
    fi
  fi

  # Translation (extract from debug logs if available)
  if [[ $line =~ "translation_completed" ]] && [[ $line =~ latency_ms=([0-9]+) ]]; then
    echo "   🌐 Translated (${BASH_REMATCH[1]}ms)"
  fi

  # TTS result
  if [[ $line =~ "tts_completed" ]] && [[ $line =~ latency_ms=([0-9]+) ]]; then
    echo "   🔊 TTS: ${BASH_REMATCH[1]}ms"
  fi

  # Audio padding
  if [[ $line =~ "Audio padded" ]] && [[ $line =~ padding_ms=([0-9]+) ]]; then
    echo "   ⏱️  Padded: +${BASH_REMATCH[1]}ms silence"
  fi

  # Final result
  if [[ $line =~ "fragment_processed" ]]; then
    # Extract total time
    total_time=""
    if [[ $line =~ total_time_ms=([0-9]+) ]]; then
      total_time=" (total: ${BASH_REMATCH[1]}ms)"
    fi

    if [[ $line =~ "status=partial" ]]; then
      echo "   ✅ DUBBED${total_time}"
    elif [[ $line =~ "status=failed" ]]; then
      echo "   ❌ FAILED (using original audio)"
    elif [[ $line =~ "status=success" ]]; then
      echo "   ✅ DUBBED${total_time}"
    fi
  fi
done
