import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:hive/hive.dart';

part 'game.freezed.dart';
part 'game.g.dart';

@HiveType(typeId: 1)
@freezed
class Game with _$Game {
  const factory Game({
    @HiveField(0) required String id,
    @HiveField(1) required String sport,
    @HiveField(2) required String homeTeam,
    @HiveField(3) required String awayTeam,
    @HiveField(4) required DateTime scheduledAt,
    @HiveField(5) String? status,
    @HiveField(6) Convergence? convergence,
    @HiveField(7) Grade? ourProcess,
    @HiveField(8) Grade? aiProcess,
    @HiveField(9) Pick? pick,
  }) = _Game;

  factory Game.fromJson(Map<String, dynamic> json) => _$GameFromJson(json);
}

@HiveType(typeId: 2)
@freezed
class Grade with _$Grade {
  const factory Grade({
    @HiveField(0) required String grade,
    @HiveField(1) required double score,
    @HiveField(2) required double confidence,
    @HiveField(3) String? thesis,
    @HiveField(4) List<String>? keyFactors,
    @HiveField(5) Map<String, dynamic>? details,
  }) = _Grade;

  factory Grade.fromJson(Map<String, dynamic> json) => _$GradeFromJson(json);
}

@HiveType(typeId: 3)
@freezed
class Convergence with _$Grade {
  const factory Convergence({
    @HiveField(0) required String status,
    @HiveField(1) required double consensusScore,
    @HiveField(2) required String consensusGrade,
    @HiveField(3) required double delta,
    @HiveField(4) required double variance,
  }) = _Convergence;

  factory Convergence.fromJson(Map<String, dynamic> json) => 
      _$ConvergenceFromJson(json);
}

@HiveType(typeId: 4)
@freezed
class Pick with _$Pick {
  const factory Pick({
    @HiveField(0) required String id,
    @HiveField(1) required String side,
    @HiveField(2) required String grade,
    @HiveField(3) required double confidence,
    @HiveField(4) String? sizing,
    @HiveField(5) String? result,
    @HiveField(6) double? profit,
    @HiveField(7) required DateTime createdAt,
  }) = _Pick;

  factory Pick.fromJson(Map<String, dynamic> json) => _$PickFromJson(json);
}

enum ConvergenceStatus {
  lock,
  aligned,
  divergent,
  conflict;

  String get displayName => switch (this) {
    ConvergenceStatus.lock => 'LOCK',
    ConvergenceStatus.aligned => 'ALIGNED',
    ConvergenceStatus.divergent => 'DIVERGENT',
    ConvergenceStatus.conflict => 'CONFLICT',
  };

  String get emoji => switch (this) {
    ConvergenceStatus.lock => '🔒',
    ConvergenceStatus.aligned => '✅',
    ConvergenceStatus.divergent => '⚠️',
    ConvergenceStatus.conflict => '❌',
  };

  int get colorValue => switch (this) {
    ConvergenceStatus.lock => 0xFF10B981,
    ConvergenceStatus.aligned => 0xFF38BDF8,
    ConvergenceStatus.divergent => 0xFFF59E0B,
    ConvergenceStatus.conflict => 0xFFEF4444,
  };
}
