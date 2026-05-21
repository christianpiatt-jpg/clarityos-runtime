from flask import Flask, jsonify, request
import dashboard_data as data

app = Flask(__name__)

@app.get("/lanes")
def lanes():
    return jsonify(data.get_lanes())

@app.get("/global")
def global_index():
    return jsonify(data.get_global_index())

@app.get("/lane/<lane>")
def lane_index(lane):
    return jsonify(data.get_lane_index(lane))

@app.get("/basin/<lane>")
def basin(lane):
    return jsonify(data.get_basin(lane))

@app.get("/drift/<lane>")
def drift(lane):
    return jsonify(data.get_drift(lane))

@app.get("/forecast/<lane>")
def forecast(lane):
    return jsonify(data.get_forecast(lane))

@app.get("/document")
def document():
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "Missing path"}), 400
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return jsonify({"path": path, "content": f.read()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)