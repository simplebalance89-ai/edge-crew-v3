import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';
import '../models/game.dart';
import '../models/user.dart';

part 'api_service.g.dart';

@RestApi(baseUrl: "https://api.edgecrew.io")
abstract class ApiService {
  factory ApiService(Dio dio, {String baseUrl}) = _ApiService;

  @GET("/health")
  Future<HealthStatus> checkHealth();

  @GET("/api/games")
  Future<List<Game>> getGames(@Query("sport") String? sport);

  @GET("/api/games/{id}")
  Future<Game> getGame(@Path("id") String id);

  @POST("/api/games/{id}/grade")
  Future<Convergence> gradeGame(@Path("id") String id);

  @GET("/api/picks")
  Future<List<Pick>> getPicks();

  @POST("/api/picks")
  Future<Pick> createPick(@Body() PickRequest request);

  @GET("/api/stream/{gameId}")
  Stream<GameUpdate> streamGameUpdates(@Path("gameId") String gameId);

  @GET("/api/user/profile")
  Future<UserProfile> getUserProfile();

  @PUT("/api/user/profile")
  Future<UserProfile> updateProfile(@Body() UserProfile profile);

  @GET("/api/bankroll")
  Future<Bankroll> getBankroll();

  @POST("/api/bankroll/transaction")
  Future<Bankroll> addTransaction(@Body() Transaction transaction);
}

class HealthStatus {
  final String status;
  final String version;

  HealthStatus({required this.status, required this.version});

  factory HealthStatus.fromJson(Map<String, dynamic> json) => HealthStatus(
        status: json['status'],
        version: json['version'],
      );
}

class PickRequest {
  final String gameId;
  final String side;
  final String grade;
  final double confidence;
  final String? sizing;

  PickRequest({
    required this.gameId,
    required this.side,
    required this.grade,
    required this.confidence,
    this.sizing,
  });

  Map<String, dynamic> toJson() => {
        'gameId': gameId,
        'side': side,
        'grade': grade,
        'confidence': confidence,
        'sizing': sizing,
      };
}

class GameUpdate {
  final String gameId;
  final String type;
  final Map<String, dynamic> data;
  final DateTime timestamp;

  GameUpdate({
    required this.gameId,
    required this.type,
    required this.data,
    required this.timestamp,
  });

  factory GameUpdate.fromJson(Map<String, dynamic> json) => GameUpdate(
        gameId: json['gameId'],
        type: json['type'],
        data: json['data'],
        timestamp: DateTime.parse(json['timestamp']),
      );
}

class Bankroll {
  final double currentBalance;
  final double totalWagered;
  final double totalProfit;
  final double roi;
  final int wins;
  final int losses;
  final int pushes;

  Bankroll({
    required this.currentBalance,
    required this.totalWagered,
    required this.totalProfit,
    required this.roi,
    required this.wins,
    required this.losses,
    required this.pushes,
  });

  factory Bankroll.fromJson(Map<String, dynamic> json) => Bankroll(
        currentBalance: json['currentBalance'].toDouble(),
        totalWagered: json['totalWagered'].toDouble(),
        totalProfit: json['totalProfit'].toDouble(),
        roi: json['roi'].toDouble(),
        wins: json['wins'],
        losses: json['losses'],
        pushes: json['pushes'],
      );
}

class Transaction {
  final String type;
  final double amount;
  final String? description;

  Transaction({
    required this.type,
    required this.amount,
    this.description,
  });

  Map<String, dynamic> toJson() => {
        'type': type,
        'amount': amount,
        'description': description,
      };
}
