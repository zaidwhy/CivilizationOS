import { Component, type ReactNode } from "react";

type State = { error: Error | null };

/** Catches render-time errors so a single broken panel can't blank the whole app. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error("CivilizationOS render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <pre
          style={{
            color: "#ff9b9b",
            background: "#0b0e14",
            padding: 24,
            margin: 0,
            height: "100vh",
            whiteSpace: "pre-wrap",
            fontSize: 13,
          }}
        >
          {this.state.error.stack || this.state.error.message}
        </pre>
      );
    }
    return this.props.children;
  }
}
